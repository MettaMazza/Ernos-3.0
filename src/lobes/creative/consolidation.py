"""
Memory Consolidation - Extracted from DreamerAbility.
Handles episodic processing, user bios, narrative synthesis, and lesson extraction.
"""
import json
import logging
import datetime
from pathlib import Path

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
            
            narrative = await self.synthesize_narrative()
            if narrative:
                results.append(f"Narrative: {len(narrative)} chars")
                await self.extract_lessons_from_narrative(narrative)
                results.append("Lessons: Extracted")
            
            logger.info(f"Consolidation Complete: {', '.join(results)}")
            return f"Memory Consolidation Complete: {', '.join(results)}"
            
        except Exception as e:
            logger.error(f"Consolidation Error: {e}")
            return f"Consolidation Failed: {e}"
    
    async def process_episodic_memories(self) -> int:
        """Process unprocessed episodic memory files."""
        count = 0
        dirs_to_check = [
            Path("memory/episodic"),
            Path("memory/core/episodic")
        ]
        
        users_dir = Path("memory/users")
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
        users_dir = Path("memory/users")
        
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
                        except Exception:
                            pass
                
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
                        except Exception:
                            pass
                    
                    profile["bio"] = bio.strip()
                    profile["bio_updated"] = datetime.datetime.now().isoformat()
                    
                    with open(profile_path, 'w') as f:
                        json.dump(profile, f, indent=2)
                    
                    users_updated += 1
                    logger.info(f"Updated bio for {folder_name}")
                    
            except Exception as e:
                logger.warning(f"Bio update failed for {user_folder.name}: {e}")
        
        return users_updated
    
    async def synthesize_narrative(self) -> str:
        """Generate autobiographical narrative from recent experiences."""
        all_content = []
        
        dirs_to_scan = [
            Path("memory/core/episodic"),
            Path("memory/episodic")
        ]
        
        users_dir = Path("memory/users")
        if users_dir.exists():
            for user_folder in users_dir.iterdir():
                if user_folder.is_dir():
                    dirs_to_scan.append(user_folder / "episodic")
        
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
                except Exception:
                    pass
        
        if not all_content:
            logger.info("No content for narrative synthesis")
            return ""
        
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
                auto_dir = Path("memory/core/autobiographies")
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
                        {"cycle": cycle_num, "type": "autobiography"}
                    )
                except Exception:
                    pass
                
                return narrative
                
        except Exception as e:
            logger.error(f"Narrative synthesis failed: {e}")
        
        return ""
    
    async def extract_lessons_from_narrative(self, narrative: str):
        """Auto-extract lessons from the synthesized narrative."""
        from src.memory.lessons import LessonManager
        from src.privacy.scopes import PrivacyScope
        
        engine = self.bot.engine_manager.get_active_engine()
        prompt = (
            "Extract 1-3 key lessons from this narrative.\n"
            "Return ONLY a JSON array of strings, each a lesson.\n"
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
                            scope=PrivacyScope.CORE,
                            source="narrative_synthesis",
                            confidence=0.7
                        )
                        logger.info(f"Auto-extracted lesson: {lesson[:50]}...")
                        
        except Exception as e:
            logger.warning(f"Lesson extraction failed: {e}")
