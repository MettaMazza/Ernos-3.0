"""
Backup Restore - Handles context import and state restoration.
"""
import json
import logging
from pathlib import Path
from typing import Tuple

from .verify import BackupVerifier
from src.privacy.scopes import ScopeManager

logger = logging.getLogger("Backup.Restore")


class BackupRestorer:
    """Handles verification and restoration of user context."""
    
    def __init__(self, bot=None):
        self.bot = bot
        self._verifier = BackupVerifier()
    
    async def import_user_context(self, user_id: int, data: dict) -> Tuple[bool, str]:
        """
        Verify and restore user context from export.
        
        Performs TRUE STATE RESTORATION:
        - Restores files to disk
        - Rebuilds WorkingMemory
        - Re-embeds content into VectorStore
        - Restores KG nodes
        """
        # Step 1: Verify backup authenticity
        is_valid, reason = self._verifier.verify_backup(data)
        if not is_valid:
            logger.error(f"Backup verification failed: {reason}")
            return False, f"Backup verification failed: {reason}"
        
        # Step 2: Verify user_id matches
        if data.get("user_id") != user_id:
            logger.error(f"Import rejected: user_id mismatch")
            return False, "Access Denied: This backup belongs to a different user."
            
        restored_files = 0
        restored_traces = 0
        restored_kg = 0
        restored_turns = 0
        restored_vectors = 0
        
        # Step 3a: Restore user silo files to disk
        user_silo = ScopeManager.get_user_home(user_id)  # Handles CORE + humanized folder names
        
        context = data.get("context", {})
        for rel_path, content in context.items():
            if content.startswith("[Read Error:"):
                continue
            file_path = user_silo / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            restored_files += 1
        
        # Step 3b: Restore public timeline
        public_timeline = data.get("public_timeline", {})
        if public_timeline:
            public_silo = Path("memory/public/users") / str(user_id)
            public_silo.mkdir(parents=True, exist_ok=True)
            for rel_path, content in public_timeline.items():
                if content.startswith("[Read Error:"):
                    continue
                file_path = public_silo / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                restored_files += 1
        
        # Step 3c: Consolidate traces
        all_trace_content = ""
        for rel_path, content in context.items():
            if "reasoning" in rel_path.lower() and content and not content.startswith("[Read Error:"):
                all_trace_content += content
                restored_traces += 1
        
        traces = data.get("traces", {})
        for trace_name, content in traces.items():
            if content and not content.startswith("[Read Error:"):
                all_trace_content += content
                restored_traces += 1
        
        if all_trace_content:
            trace_path = user_silo / "reasoning.log"
            trace_path.write_text(all_trace_content, encoding="utf-8")
        
        # Step 4: Rebuild in-memory state
        try:
            if self.bot and hasattr(self.bot, 'hippocampus'):
                hippocampus = self.bot.hippocampus
                
                async def restore_log(content, forced_scope=None):
                    count = 0
                    if not content:
                        return 0
                    for line in content.strip().split("\n"):
                        if line.strip():
                            try:
                                turn = json.loads(line)
                                user_msg = turn.get("user", "")
                                bot_msg = turn.get("bot", "")
                                if user_msg and bot_msg:
                                    scope = forced_scope if forced_scope else turn.get("scope", "PRIVATE")
                                    await hippocampus.working.add_turn(
                                        user_id=str(user_id),
                                        user_msg=user_msg,
                                        bot_msg=bot_msg,
                                        scope=scope
                                    )
                                    count += 1
                            except json.JSONDecodeError:
                                continue
                    return count
                
                # Restore split logs
                restored_turns += await restore_log(context.get("context_private.jsonl", ""), "PRIVATE")
                restored_turns += await restore_log(context.get("context_public.jsonl", ""), "PUBLIC")
                restored_turns += await restore_log(context.get("context.jsonl", ""), None)
                
                logger.info(f"Restored {restored_turns} conversation turns")
                
                # Fallback for legacy backups
                if restored_turns == 0 and all_trace_content:
                    recent_trace = all_trace_content[-4000:]
                    await hippocampus.working.add_turn(
                        user_id=str(user_id),
                        user_msg="[SYSTEM: Context restored from backup]",
                        bot_msg=f"[RESTORED HISTORY]\n{recent_trace}",
                        scope="PRIVATE"
                    )
                    restored_turns += 1
                
                # Re-embed context into VectorStore
                for rel_path, content in context.items():
                    if rel_path.endswith(".jsonl") or content.startswith("[Read Error:") or len(content) < 5:
                        continue
                    try:
                        chunk = content[:5000]
                        embedding = hippocampus.embedder.get_embedding(chunk)
                        if embedding:
                            # Determine scope from file path
                            if "private" in rel_path.lower() or "persona" in rel_path.lower() or "reasoning" in rel_path.lower():
                                vec_scope = "PRIVATE"
                            else:
                                vec_scope = "PUBLIC"
                            hippocampus.vector_store.add_element(
                                text=chunk,
                                embedding=embedding,
                                metadata={
                                    "source": f"restored:{rel_path}",
                                    "user_id": str(user_id),
                                    "user_ids": [str(user_id)],
                                    "scope": vec_scope
                                }
                            )
                            restored_vectors += 1
                    except Exception as e:
                        logger.warning(f"Vector embedding failed for {rel_path}: {e}")
                        
                logger.info(f"Re-embedded {restored_vectors} files into VectorStore")
                
        except Exception as e:
            logger.warning(f"In-memory state rebuild partial: {e}")
        
        # Step 5: Restore KG nodes
        kg_nodes = data.get("knowledge_graph", [])
        if kg_nodes:
            try:
                from src.memory.graph import KnowledgeGraph
                from src.memory.types import GraphLayer
                
                kg = KnowledgeGraph()
                for node in kg_nodes:
                    name = node.get("name")
                    labels = node.get("labels", [])
                    props = node.get("properties", {})
                    
                    if labels and name:
                        label = labels[0]
                        layer = props.get("layer", "narrative")
                        try:
                            layer_enum = GraphLayer(layer) if layer else GraphLayer.NARRATIVE
                        except Exception:
                            layer_enum = GraphLayer.NARRATIVE
                            
                        kg.add_node(
                            label=label,
                            name=name,
                            layer=layer_enum,
                            properties=props,
                            user_id=user_id,
                            scope=props.get("scope", "PUBLIC")
                        )
                        restored_kg += 1
                kg.close()
            except Exception as e:
                logger.warning(f"KG restore skipped: {e}")
            
        logger.info(f"User {user_id} FULL STATE RESTORED: {restored_files} files, {restored_turns} turns, {restored_kg} KG nodes")
        return True, f"Full state restored ({restored_files} files, {restored_turns} turns, {restored_vectors} vectors, {restored_kg} KG nodes)"
