from ..base import BaseAbility
from src.tools.registry import ToolRegistry
import logging

logger = logging.getLogger("Lobe.Interaction.Researcher")

class ResearchAbility(BaseAbility):
    """
    Web Search & Synthesis.
    """
    async def execute(self, query: str):
        logger.info(f"Researcher searching for: {query}")
        # Use Tool Registry
        # Use Tool Registry
        raw_results = await ToolRegistry.execute("search_web", query)
        
        # Synthesize with LLM
        engine = self.bot.engine_manager.get_active_engine()
        prompt = (
            f"ROLE: Research Assistant.\n"
            f"QUERY: {query}\n"
            f"RAW DATA: {raw_results}\n\n"
            f"TASK: Synthesize these search results into a concise summary."
        )
        
        try:
            synthesis = await self.bot.loop.run_in_executor(
                None, 
                engine.generate_response, 
                prompt
            )
            
            # 3. EXTRACTION
            # Convert report into Graph Nodes
            await self._extract_and_store_knowledge(synthesis)
            
            return f"Research Findings:\n{synthesis}"
        except Exception as e:
            return f"Research Synthesis Failed: {e}\nRaw Data: {raw_results}"

    async def _extract_and_store_knowledge(self, report: str):
        """
        Extracts structured knowledge from text and saves to Neo4j.
        """
        logger.info("Researcher: Extracting Knowledge Graph Nodes...")
        try:
             memory_lobe = self.bot.cerebrum.get_lobe_by_name("MemoryLobe")
             if not memory_lobe:
                 return
             
             ontologist = memory_lobe.get_ability("OntologistAbility")
             if not ontologist:
                 logger.error("Researcher: OntologistAbility not found.")
                 return

             # REAL GRAPH STORAGE via Ontologist
             # We store the session itself as a high-level node
             # "System" -> [RESEARCHED] -> "Topic"
             
             # Extract topic from first line (naive heuristic for now)
             # "### Deep Research: [Topic]"
             first_line = report.split('\n')[0]
             topic = "Unknown Topic"
             if "Deep Research:" in first_line:
                 topic = first_line.split("Deep Research:")[1].strip()
                 
             # 1. Create Topic Node
             await ontologist.execute("System", "RESEARCHED", topic)
             
             # 2. Store Summary as Property (or separate node if large)
             # For v3.1 stability, we just link the topic.
             # Future: Parse report for sub-claims.
             
             logger.info(f"Researcher: Stored knowledge for '{topic}' via Ontologist.")
              
        except Exception as e:
             logger.warning(f"Graph Extraction warning: {e}")

