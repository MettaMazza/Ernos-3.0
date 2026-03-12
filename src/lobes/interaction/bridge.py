from ..base import BaseAbility
import logging
import os
from pathlib import Path
from src.privacy.scopes import ScopeManager, PrivacyScope
from src.core.data_paths import data_dir

logger = logging.getLogger("Lobe.Interaction.Bridge")

class BridgeAbility(BaseAbility):
    """
    The Bridge manages PUBLIC and SHARED memory.
    It allows cross-pollination of safe ideas between contexts.
    
    Queries:
    1. Public files in memory/public/
    2. VectorStore with scope=PUBLIC
    3. KnowledgeGraph for system-wide nodes (user_id=NULL)
    """
    def __init__(self, lobe):
        super().__init__(lobe)
    
    async def execute(self, query: str) -> str:
        logger.info(f"Bridge accessing public memory: {query}")
        
        results = []
        results.append(f"### Bridge Access: '{query}'")
        
        # 1. Search public files
        public_dir = data_dir() / "public"
        file_matches = []
        if public_dir.exists():
            for file_path in public_dir.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        if query.lower() in content.lower():
                            # Extract relevant snippet
                            idx = content.lower().find(query.lower())
                            start = max(0, idx - 100)
                            end = min(len(content), idx + 200)
                            snippet = content[start:end].strip()
                            file_matches.append(f"- **{file_path.name}**: ...{snippet}...")
                    except Exception as e:
                        logger.warning(f"Bridge file read error: {e}")
        
        if file_matches:
            results.append("\n**Public Files:**")
            results.extend(file_matches[:5])  # Limit to top 5
        
        # 2. Query VectorStore with PUBLIC scope
        vector_results = []
        try:
            if self.hippocampus and self.hippocampus.vector_store:
                # Chunk query to prevent HTTP 500 without losing data
                from src.memory.chunking import chunk_text
                chunks = chunk_text(query)
                # For queries, use first chunk (most relevant info usually at start)
                query_vec = self.hippocampus.embedder.get_embedding(chunks[0])
                if query_vec:
                    # Retrieve with PUBLIC scope filter
                    matches = self.hippocampus.vector_store.retrieve(
                        query_vec, 
                        scope=PrivacyScope.PUBLIC,
                        top_k=3
                    )
                    for match in matches:
                        text = match.get("text", "")[:200]
                        vector_results.append(f"- {text}...")
        except Exception as e:
            logger.warning(f"Bridge vector query error: {e}")
        
        if vector_results:
            results.append("\n**Public Vector Memory:**")
            results.extend(vector_results)
        
        # 3. Query KnowledgeGraph for SYSTEM nodes (user_id=-1, explicitly marked as global)
        # NOTE: We now use -1 for system nodes, not NULL. NULL indicates orphaned data (bug).
        graph_results = []
        try:
            if self.hippocampus and self.hippocampus.graph:
                with self.hippocampus.graph.driver.session() as session:
                    # Query for SYSTEM nodes (user_id = -1) - explicitly marked as public/global
                    # Also include attribution info for transparency
                    cypher = """
                    MATCH (n)
                    WHERE n.user_id = -1 
                    AND (toLower(n.name) CONTAINS toLower($search_term) 
                         OR toLower(coalesce(n.description, '')) CONTAINS toLower($search_term))
                    RETURN n.name as name, labels(n) as labels, n.description as desc, 
                           n._orphan_source as source, n.created_by as created_by
                    LIMIT 5
                    """
                    result = session.run(cypher, search_term=query)
                    for record in result:
                        name = record["name"]
                        labels = record["labels"]
                        desc = record.get("desc", "")[:100] if record.get("desc") else ""
                        # Include attribution if available
                        source = record.get("source") or record.get("created_by") or "system"
                        graph_results.append(f"- **{name}** ({', '.join(labels)}) [via: {source}]: {desc}")
        except Exception as e:
            logger.warning(f"Bridge graph query error: {e}")
        
        if graph_results:
            results.append("\\n**Public Knowledge Graph (System Data):**")
            results.extend(graph_results)
        
        # Summary
        total = len(file_matches) + len(vector_results) + len(graph_results)
        if total == 0:
            results.append("\n*No public knowledge found matching this query.*")
        else:
            results.append(f"\n*Found {total} public knowledge items.*")
        
        return "\n".join(results)

