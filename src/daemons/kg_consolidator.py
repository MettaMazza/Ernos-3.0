"""
KG Consolidator Daemon

Autonomously extracts entities and relationships from conversations
and persists them to Neo4j with proper scope tagging.

Trigger: After every 5 turns (event-driven, not time-based).
"""

import logging
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

from src.privacy.scopes import PrivacyScope, ScopeManager

logger = logging.getLogger("Daemon.KGConsolidator")


class KGConsolidator:
    """
    Background Knowledge Graph consolidation daemon.
    
    Triggered after every CONSOLIDATION_THRESHOLD turns to extract
    entities and relationships from recent conversations.
    """
    
    CONSOLIDATION_THRESHOLD = 5  # Consolidate after this many turns
    
    def __init__(self, bot):
        self.bot = bot
        self._turn_counter = 0
        self._pending_interactions: List[Dict] = []
        self._is_consolidating = False
        
    def record_turn(self, user_id: int, user_msg: str, bot_msg: str, channel_id: int, is_dm: bool = False, salience: float = 0.5):
        """
        Called by hippocampus after each interaction.
        Tracks turns and triggers consolidation when threshold reached.
        """
        scope = ScopeManager.get_scope(user_id, channel_id, is_dm=is_dm)
        
        self._pending_interactions.append({
            "user_id": user_id,
            "user_msg": user_msg,
            "bot_msg": bot_msg,
            "scope": scope.name,
            "timestamp": datetime.now().isoformat(),
            "salience": salience
        })
        
        # Weighted turn counting based on salience
        if salience > 0.8:
            # High importance: Trigger immediate consolidation
            logger.info(f"High salience ({salience:.2f}) triggered immediate KG consolidation.")
            self._turn_counter += self.CONSOLIDATION_THRESHOLD
        elif salience < 0.3:
            # Low importance: Ignore (save tokens)
            logger.debug(f"Low salience ({salience:.2f}) ignored for KG consolidation.")
            return
        else:
            # Normal importance
            self._turn_counter += 1
            
        logger.debug(f"KG turn counter: {self._turn_counter}/{self.CONSOLIDATION_THRESHOLD}")
        
        # Trigger consolidation if threshold reached
        if self._turn_counter >= self.CONSOLIDATION_THRESHOLD:
            asyncio.create_task(self._consolidate())
            self._turn_counter = 0
            
    async def _consolidate(self):
        """
        Extract entities/relationships from pending interactions
        and persist to Neo4j with scope tags.
        """
        if self._is_consolidating:
            logger.debug("Consolidation already in progress, skipping")
            return
            
        if not self._pending_interactions:
            return
            
        self._is_consolidating = True
        batch = self._pending_interactions.copy()
        self._pending_interactions.clear()
        
        logger.info(f"KG Consolidation started: {len(batch)} interactions")
        
        try:
            # Group by scope for processing
            by_scope = {}
            for interaction in batch:
                scope = interaction["scope"]
                if scope not in by_scope:
                    by_scope[scope] = []
                by_scope[scope].append(interaction)
            
            # Process each scope batch
            total_extracted = 0
            for scope_name, interactions in by_scope.items():
                extracted = await self._extract_and_store(interactions, scope_name)
                total_extracted += extracted
                
            logger.info(f"KG Consolidation complete: {total_extracted} relationships extracted")
            
            # Classify unlayered nodes after each consolidation
            await self._classify_unlayered_nodes()
            
        except Exception as e:
            logger.error(f"KG Consolidation failed: {e}")
        finally:
            self._is_consolidating = False
            
    async def _extract_and_store(self, interactions: List[Dict], scope_name: str) -> int:
        """
        Use LLM to extract entities/relationships from a batch of interactions.
        Returns count of relationships stored.
        """
        # Build conversation text for LLM
        conversation_text = ""
        user_ids = set()
        for i in interactions:
            conversation_text += f"User: {i['user_msg']}\nErnos: {i['bot_msg']}\n---\n"
            user_ids.add(i["user_id"])
        
        # Get user_id for PRIVATE scope (single user in DM)
        user_id = list(user_ids)[0] if len(user_ids) == 1 else None
        
        # Load extraction prompt
        try:
            from src.core.secure_loader import load_prompt
            template = load_prompt("src/prompts/kg_extraction.txt")
            prompt = template.format(conversation=conversation_text)
        except FileNotFoundError:
            # Fallback prompt
            prompt = f"""Extract entities and relationships from this conversation.
Output a JSON array of objects with: subject, predicate, object, confidence (0-1).
Only extract factual relationships, not conversational filler.

Conversation:
{conversation_text}

JSON Output:"""
        
        # Use inference engine
        try:
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                logger.warning("No inference engine available for KG extraction")
                return 0
                
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            # Parse JSON from response
            relationships = self._parse_extraction(response)
            
            # Store in Neo4j
            stored = 0
            if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus.graph:
                graph = self.bot.hippocampus.graph
                
                # Valid layer names for validation
                from src.memory.types import GraphLayer
                valid_layers = {l.value for l in GraphLayer}
                
                for rel in relationships:
                    if rel.get("confidence", 0) >= 0.7:  # Confidence threshold
                        # Quality guards — reject LLM junk
                        subj = rel.get("subject", "")
                        pred = rel.get("predicate", "")
                        obj = rel.get("object", "")
                        if len(pred) > 50:
                            logger.debug(f"KG: Dropping junk rel_type ({len(pred)} chars): {pred[:50]}...")
                            continue
                        if len(subj) < 2 or len(subj) > 100 or len(obj) < 2 or len(obj) > 100:
                            logger.debug(f"KG: Dropping bad entity names: '{subj}' / '{obj}'")
                            continue
                        
                        # Use LLM-classified layer, validate against enum
                        raw_layer = rel.get("layer", "narrative").lower().strip()
                        layer = raw_layer if raw_layer in valid_layers else "narrative"
                        
                        # STRICT IDENTITY: Always require user_id
                        target_user_id = user_id if user_id else (list(user_ids)[0] if user_ids else None)
                        
                        if not target_user_id:
                            logger.error("CRITICAL: Attempted to write KG fact without user_id. Dropping.")
                            continue
                        
                        # Create nodes explicitly so they have proper labels/scope/layer
                        graph.add_node(
                            label="Entity", name=subj, layer=layer,
                            user_id=target_user_id, scope=scope_name
                        )
                        graph.add_node(
                            label="Entity", name=obj, layer=layer,
                            user_id=target_user_id, scope=scope_name
                        )
                            
                        graph.add_relationship(
                            source_name=subj,
                            rel_type=pred,
                            target_name=obj,
                            layer=layer,
                            scope=scope_name,
                            user_id=target_user_id,
                            source="consolidator"
                        )
                        stored += 1
                        
            logger.debug(f"Stored {stored} relationships for scope {scope_name}")
            return stored
            
        except Exception as e:
            logger.error(f"KG extraction failed: {e}")
            return 0
            
    def _parse_extraction(self, response: str) -> List[Dict]:
        """
        Parse LLM response to extract JSON array of relationships.
        Handles various response formats.
        """
        try:
            # Try to find JSON array in response
            import re
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return []
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse KG extraction response: {response[:100]}")
            return []
            
    def force_consolidate(self):
        """Manual trigger for consolidation (e.g., before shutdown)."""
        if self._pending_interactions:
            asyncio.create_task(self._consolidate())

    async def _classify_unlayered_nodes(self, batch_size: int = 20):
        """
        Classify nodes that have no cognitive layer assigned.
        Queries Neo4j for unlayered nodes and uses LLM to assign layers.
        """
        try:
            if not (hasattr(self.bot, 'hippocampus') and self.bot.hippocampus.graph):
                return
            
            graph = self.bot.hippocampus.graph
            driver = getattr(graph, 'driver', None) or getattr(graph, '_driver', None)
            if not driver:
                logger.debug("KG layer classification: no Neo4j driver available")
                return
            
            # Query unlayered nodes with their relationships for context
            query = """
            MATCH (n)
            WHERE n.layer IS NULL
            OPTIONAL MATCH (n)-[r]-(m)
            WITH n, collect(DISTINCT {rel: type(r), other: m.name})[..3] AS rels
            RETURN n.name AS name, labels(n) AS labels, rels
            LIMIT $batch_size
            """
            
            with driver.session() as session:
                result = session.run(query, batch_size=batch_size)
                nodes = [dict(record) for record in result]
            
            if not nodes:
                logger.debug("KG layer classification: no unlayered nodes found")
                return
            
            logger.info(f"KG layer classification: processing {len(nodes)} unlayered nodes")
            
            # Build LLM prompt
            from src.memory.types import GraphLayer
            valid_layers = [l.value for l in GraphLayer]
            
            node_descriptions = []
            for node in nodes:
                name = node.get('name', 'unknown')
                labels = node.get('labels', [])
                rels = node.get('rels', [])
                rel_desc = ", ".join(
                    f"{r.get('rel', '?')}->{r.get('other', '?')}" 
                    for r in rels if r.get('other')
                ) or "no relationships"
                node_descriptions.append(f"- {name} (labels: {labels}, rels: {rel_desc})")
            
            prompt = (
                f"Classify each knowledge graph node into ONE of these 26 cognitive layers:\n"
                f"{', '.join(valid_layers)}\n\n"
                f"Nodes to classify:\n"
                + "\n".join(node_descriptions) +
                f"\n\nOutput a JSON array of objects: [{{\"name\": \"...\", \"layer\": \"...\"}}]"
                f"\nRespond with ONLY the JSON array."
            )
            
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                return
            
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            # Parse response — find outermost JSON array with bracket matching
            start = response.find('[')
            end = response.rfind(']')
            if start == -1 or end == -1 or end <= start:
                logger.debug("KG layer classification: no JSON array in LLM response")
                return
            
            try:
                classifications = json.loads(response[start:end + 1])
            except json.JSONDecodeError as e:
                logger.warning(f"KG layer classification: JSON parse failed: {e}")
                return
            valid_set = set(valid_layers)
            updated = 0
            
            with driver.session() as session:
                for item in classifications:
                    name = item.get("name", "")
                    layer = item.get("layer", "").lower().strip()
                    if name and layer in valid_set:
                        session.run(
                            "MATCH (n {name: $name}) WHERE n.layer IS NULL SET n.layer = $layer",
                            name=name, layer=layer
                        )
                        updated += 1
            
            logger.info(f"KG layer classification: updated {updated}/{len(nodes)} nodes")
            
        except Exception as e:
            logger.error(f"KG layer classification failed: {e}")
