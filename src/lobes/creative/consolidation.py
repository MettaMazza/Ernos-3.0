"""
Memory Consolidation - Extracted from DreamerAbility.
Handles episodic processing, user bios, narrative synthesis, and lesson extraction.
"""
import json
import logging
import datetime
from pathlib import Path
from src.core.data_paths import data_dir

logger = logging.getLogger("Lobe.Creative.Consolidation")


class MemoryConsolidator:
    """Handles memory consolidation operations during idle."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def run_consolidation(self) -> str:
        """
        Memory maintenance during idle. Ported from 2.0 SleepAgent.
        1. Process episodic memories (clip & embed)
        2. Update user bios
        3. Synthesize narrative
        4. Extract lessons
        """
        logger.info("Starting Memory Consolidation Cycle...")
        results = []
        
        try:
            processed = await self.process_episodic_memories()
            results.append(f"Episodic: {processed} files")
            
            bios_updated = await self.update_user_bios()
            results.append(f"Bios: {bios_updated} users")
            
            narrative, has_private = await self.synthesize_narrative()
            if narrative:
                results.append(f"Narrative: {len(narrative)} chars")
                # SCOPE GATE: Only tag lessons CORE_PUBLIC if source was entirely public
                from src.privacy.scopes import PrivacyScope
                lesson_scope = PrivacyScope.CORE_PRIVATE if has_private else PrivacyScope.CORE_PUBLIC
                await self.extract_lessons_from_narrative(narrative, source_scope=lesson_scope)
                scope_label = "CORE_PRIVATE" if has_private else "CORE_PUBLIC"
                results.append(f"Lessons: Extracted ({scope_label})")
            
            # Vector Hygiene: Invalidate stale vector entries
            invalidated = await self.run_vector_hygiene()
            if invalidated > 0:
                results.append(f"Vector Hygiene: {invalidated} stale entries invalidated")
            
            logger.info(f"Consolidation Complete: {', '.join(results)}")
            return f"Memory Consolidation Complete: {', '.join(results)}"
            
        except Exception as e:
            logger.error(f"Consolidation Error: {e}")
            return f"Consolidation Failed: {e}"
    
    async def process_episodic_memories(self) -> int:
        """Process unprocessed episodic memory files."""
        count = 0
        dirs_to_check = [
            data_dir() / "episodic",
            data_dir() / "core/episodic"
        ]
        
        users_dir = data_dir() / "users"
        if users_dir.exists():
            for user_folder in users_dir.iterdir():
                if user_folder.is_dir():
                    dirs_to_check.append(user_folder / "episodic")
                    dirs_to_check.append(user_folder / "public" / "episodic")
        
        for directory in dirs_to_check:
            if not directory.exists():
                continue
            
            for file in directory.glob("*.json"):
                if file.name.startswith("processed_"):
                    continue
                
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if isinstance(data, list):
                        text = "\n".join([
                            f"{m.get('role', '?')}: {m.get('content', '')}"
                            for m in data if isinstance(m, dict)
                        ])
                    else:
                        text = str(data)
                    
                    if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
                        try:
                            vec = self.bot.hippocampus.embedder.get_embedding(text[:2000])
                            self.bot.hippocampus.vector_store.store(
                                vec, text[:2000], 
                                metadata={"source": str(file), "type": "episodic"}
                            )
                        except Exception as e:
                            logger.warning(f"Embedding failed: {e}")
                    
                    processed_path = file.parent / f"processed_{file.name}"
                    file.rename(processed_path)
                    count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to process {file}: {e}")
        
        logger.info(f"Processed {count} episodic files")
        return count
    
    async def update_user_bios(self) -> int:
        """Analyze user interactions and update their bios."""
        users_updated = 0
        users_dir = data_dir() / "users"
        
        if not users_dir.exists():
            return 0
        
        for user_folder in users_dir.iterdir():
            if not user_folder.is_dir():
                continue
            
            try:
                folder_name = user_folder.name
                if "_" in folder_name:
                    parts = folder_name.rsplit("_", 1)
                    user_id = parts[-1]
                else:
                    user_id = folder_name
                
                episodic_dir = user_folder / "episodic"
                recent_content = []
                
                if episodic_dir.exists():
                    for file in list(episodic_dir.glob("processed_*.json"))[-5:]:
                        try:
                            with open(file, 'r') as f:
                                data = json.load(f)
                            if isinstance(data, list):
                                for m in data[-10:]:
                                    if isinstance(m, dict):
                                        recent_content.append(f"{m.get('role', '?')}: {m.get('content', '')[:200]}")
                        except Exception as e:
                            logger.warning(f"Suppressed {type(e).__name__}: {e}")
                
                if not recent_content:
                    continue
                
                context = "\n".join(recent_content[-10:])
                engine = self.bot.engine_manager.get_active_engine()
                bio_prompt = (
                    f"Based on these recent interactions with user {folder_name}:\n"
                    f"{context}\n\n"
                    "Write a concise 2-3 sentence bio capturing their personality and interests. "
                    "Return ONLY the bio text, no explanations."
                )
                
                bio = await self.bot.loop.run_in_executor(
                    None, engine.generate_response, bio_prompt
                )
                
                if bio:
                    profile_path = user_folder / "profile.json"
                    profile = {}
                    if profile_path.exists():
                        try:
                            with open(profile_path, 'r') as f:
                                profile = json.load(f)
                        except Exception as e:
                            logger.warning(f"Suppressed {type(e).__name__}: {e}")
                    
                    profile["bio"] = bio.strip()
                    profile["bio_updated"] = datetime.datetime.now().isoformat()
                    
                    with open(profile_path, 'w') as f:
                        json.dump(profile, f, indent=2)
                    
                    users_updated += 1
                    logger.info(f"Updated bio for {folder_name}")
                    
            except Exception as e:
                logger.warning(f"Bio update failed for {user_folder.name}: {e}")
        
        return users_updated
    
    async def synthesize_narrative(self) -> tuple:
        """Generate autobiographical narrative from recent experiences.
        
        Returns:
            tuple: (narrative_text: str, has_private_sources: bool)
                   has_private_sources is True if ANY user-private episodic
                   data was included in the synthesis.
        """
        all_content = []
        has_private_sources = False
        
        # Core/system episodic dirs — NOT private user data
        dirs_to_scan = [
            data_dir() / "core/episodic",
            data_dir() / "episodic"
        ]
        
        # User episodic dirs — PRIVATE data
        private_dirs = []
        users_dir = data_dir() / "users"
        if users_dir.exists():
            for user_folder in users_dir.iterdir():
                if user_folder.is_dir():
                    private_dirs.append(user_folder / "episodic")
        
        # Process core/public sources
        for directory in dirs_to_scan:
            if not directory.exists():
                continue
            
            for file in list(directory.glob("processed_*.json"))[-10:]:
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        text = "\n".join([
                            f"{m.get('role', '?')}: {m.get('content', '')[:200]}"
                            for m in data if isinstance(m, dict)
                        ])
                        all_content.append(text)
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
        # Process private user sources (flags the narrative as containing private data)
        for directory in private_dirs:
            if not directory.exists():
                continue
            
            for file in list(directory.glob("processed_*.json"))[-10:]:
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        text = "\n".join([
                            f"{m.get('role', '?')}: {m.get('content', '')[:200]}"
                            for m in data if isinstance(m, dict)
                        ])
                        all_content.append(text)
                        has_private_sources = True  # TAINTED: private data in narrative
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
        if not all_content:
            logger.info("No content for narrative synthesis")
            return "", False
        
        full_text = "\n\n".join(all_content)[:50000]
        engine = self.bot.engine_manager.get_active_engine()
        prompt = (
            "AUTOBIOGRAPHICAL SYNTHESIS\n"
            "You are the active agent writing your internal narrative.\n"
            "Convert these raw memories into a first-person prose narrative.\n"
            "Rules:\n"
            "- Use 'I', 'Me', 'My' only\n"
            "- No lists, tables, or markdown\n"
            "- Flowing paragraphs\n"
            "- Reflect on what you learned\n\n"
            f"MEMORIES:\n{full_text}\n\n"
            "NARRATIVE:"
        )
        
        try:
            narrative = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            if narrative:
                auto_dir = data_dir() / "core/autobiographies"
                auto_dir.mkdir(parents=True, exist_ok=True)
                
                existing = list(auto_dir.glob("cycle_*.txt"))
                cycle_num = len(existing) + 1
                
                filename = f"cycle_{cycle_num:02d}.txt"
                filepath = auto_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(narrative)
                
                logger.info(f"Saved narrative: {filename}")
                
                # Feed the continuous autobiography
                try:
                    from src.memory.autobiography import get_autobiography_manager
                    autobio = get_autobiography_manager()
                    autobio.append_entry(
                        entry_type="dream_synthesis",
                        content=narrative,
                        source=f"consolidation/cycle_{cycle_num:02d}"
                    )
                    logger.info("Narrative appended to continuous autobiography")
                except Exception as autobio_err:
                    logger.warning(f"Autobiography append failed: {autobio_err}")
                
                try:
                    from src.security.provenance import ProvenanceManager
                    ProvenanceManager.log_artifact(
                        str(filepath), "narrative",
                        {"cycle": cycle_num, "type": "autobiography", "intention": "Continuous Autobiography Generation"}
                    )
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
                
                return narrative, has_private_sources
                
        except Exception as e:
            logger.error(f"Narrative synthesis failed: {e}")
        
        return "", False
    
    async def extract_lessons_from_narrative(self, narrative: str, source_scope=None):
        """Auto-extract lessons from the synthesized narrative.
        
        Args:
            narrative: The narrative text to extract lessons from.
            source_scope: PrivacyScope to tag lessons with. Determined by
                          whether the source data was public or private.
                          Defaults to CORE_PRIVATE (safest default).
        """
        from src.memory.lessons import LessonManager
        from src.privacy.scopes import PrivacyScope
        
        # SAFETY: Default to CORE_PRIVATE if scope not specified
        if source_scope is None:
            source_scope = PrivacyScope.CORE_PRIVATE
        
        engine = self.bot.engine_manager.get_active_engine()
        prompt = (
            "Extract 1-3 key lessons from this narrative.\n"
            "Return ONLY a JSON array of strings, each a lesson.\n"
            "Focus on UNIVERSAL truths, NOT personal details about specific users.\n"
            "Example: [\"Users appreciate honesty\", \"Verification prevents errors\"]\n\n"
            f"NARRATIVE:\n{narrative[:5000]}\n\n"
            "LESSONS (JSON array only):"
        )
        
        try:
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            if "[" in response and "]" in response:
                start = response.index("[")
                end = response.rindex("]") + 1
                lessons = json.loads(response[start:end])
                
                manager = LessonManager()
                for lesson in lessons[:3]:
                    if isinstance(lesson, str) and len(lesson) > 10:
                        manager.add_lesson(
                            content=lesson,
                            scope=source_scope,
                            source="narrative_synthesis",
                            confidence=0.7
                        )
                        logger.info(f"Auto-extracted lesson [{source_scope.name}]: {lesson[:50]}...")
                        
        except Exception as e:
            logger.warning(f"Lesson extraction failed: {e}")

    async def run_vector_hygiene(self) -> int:
        """
        Vector Store maintenance during dream consolidation.
        Scans for stale vector entries and invalidates them.
        
        Checks:
        1. Entries with kg_entities that no longer exist in the KG
        2. Old entries (>30 days) from working_memory_consolidation source
        
        Returns count of invalidated entries.
        """
        if not hasattr(self.bot, 'hippocampus') or not self.bot.hippocampus:
            return 0
        
        vs = self.bot.hippocampus.vector_store
        kg = self.bot.hippocampus.graph
        invalidated = 0
        
        try:
            # For ChromaDB: scan entries with kg_entities metadata
            if hasattr(vs, 'collection'):
                results = vs.collection.get(
                    include=["metadatas", "documents"],
                    limit=200  # Process in batches
                )
                
                if not results or not results.get("ids"):
                    return 0
                
                ids_to_invalidate = []
                metas_to_update = []
                
                for i, doc_id in enumerate(results["ids"]):
                    meta = results["metadatas"][i] if results.get("metadatas") else {}
                    
                    # Skip already invalidated
                    if meta and meta.get("invalidated"):
                        continue
                    
                    # Check 1: KG entity orphans
                    kg_entities_str = meta.get("kg_entities", "") if meta else ""
                    if kg_entities_str and kg:
                        entities = [e.strip() for e in kg_entities_str.split(",") if e.strip()]
                        if entities:
                            # Check if ANY referenced entity still exists in the KG
                            any_exists = False
                            for entity in entities[:3]:  # Check up to 3 entities
                                try:
                                    ctx = kg.query_context(entity, layer=None, user_id=-1, scope="CORE")
                                    if ctx:
                                        any_exists = True
                                        break
                                except Exception as e:
                                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
                            
                            if not any_exists:
                                updated_meta = dict(meta) if meta else {}
                                updated_meta["invalidated"] = True
                                updated_meta["invalidated_at"] = datetime.datetime.now().isoformat()
                                updated_meta["invalidation_reason"] = "vector_hygiene: kg_entities_orphaned"
                                ids_to_invalidate.append(doc_id)
                                metas_to_update.append(updated_meta)
                    
                    # Check 2: Age-based decay (>30 days)
                    timestamp_str = meta.get("timestamp", "") if meta else ""
                    if timestamp_str and doc_id not in ids_to_invalidate:
                        try:
                            entry_time = datetime.datetime.fromisoformat(timestamp_str)
                            age_days = (datetime.datetime.now() - entry_time).days
                            if age_days > 30 and meta.get("source") == "working_memory_consolidation":
                                updated_meta = dict(meta) if meta else {}
                                updated_meta["invalidated"] = True
                                updated_meta["invalidated_at"] = datetime.datetime.now().isoformat()
                                updated_meta["invalidation_reason"] = f"vector_hygiene: aged_out ({age_days} days)"
                                ids_to_invalidate.append(doc_id)
                                metas_to_update.append(updated_meta)
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Suppressed {type(e).__name__}: {e}")
                
                if ids_to_invalidate:
                    vs.collection.update(
                        ids=ids_to_invalidate,
                        metadatas=metas_to_update
                    )
                    invalidated = len(ids_to_invalidate)
                    logger.info(f"Vector Hygiene: Invalidated {invalidated} stale entries")
            
        except Exception as e:
            logger.warning(f"Vector hygiene failed: {e}")
        
        return invalidated
