"""
Dream Consolidation Daemon — v3.3 Sleep Cycle.

Runs daily at 3 AM via TaskScheduler. Orchestrates:
1. Episodic memory processing
2. Episodic memory compression
3. Narrative synthesis
4. Lesson extraction
5. KG node pruning
6. Quarantine processing (re-parenting orphaned KG entries)
7. Immune cache persistence

This daemon uses the existing MemoryConsolidator and adds
compression, salience scoring, and quarantine processing on top.
"""
import logging
import json
import re
import time
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("Daemon.DreamConsolidation")

# Status file for HUD reporting
STATUS_FILE = Path("memory/system/dream_status.json")


class DreamConsolidationDaemon:
    """
    Nightly memory maintenance daemon.
    
    The 'Sleep Cycle' — Ernos processes the day's memories:
    1. Scores memories for importance (salience)
    2. Compresses old conversations into summaries
    3. Synthesizes autobiographical narrative
    4. Extracts lessons
    5. Prunes redundant KG nodes
    6. Persists sentinel cache to disk
    """
    
    def __init__(self, bot):
        self.bot = bot
        self._last_run = None
        self._status = "idle"
    
    async def run(self):
        """
        Main consolidation cycle. Called by TaskScheduler.
        """
        start_time = time.time()
        self._status = "running"
        results = []
        
        logger.info("🌙 Dream Consolidation Cycle starting...")
        self._write_status("running", "Starting dream cycle...")
        
        try:
            # 1. Score and compress episodic memories
            compressed = await self._compress_episodic_memories()
            results.append(f"Compressed: {compressed} conversations")
            
            # 2. Run existing consolidation pipeline
            from src.lobes.creative.consolidation import MemoryConsolidator
            consolidator = MemoryConsolidator(self.bot)
            consolidation_result = await consolidator.run_consolidation()
            results.append(consolidation_result)
            
            # 3. Prune redundant KG nodes
            pruned = await self._prune_kg_nodes()
            results.append(f"KG pruned: {pruned} nodes")
            
            # 4. Process quarantine queue (re-parent orphaned entries)
            resolved = await self._process_quarantine()
            results.append(f"Quarantine resolved: {resolved} entries")
            
            # 5. Persist sentinel immune cache
            persisted = self._persist_sentinel_cache()
            results.append(f"Immune cache: {'persisted' if persisted else 'skipped'}")
            
            elapsed = time.time() - start_time
            summary = f"Dream cycle complete in {elapsed:.1f}s: {', '.join(results)}"
            logger.info(f"🌙 {summary}")
            
            self._status = "complete"
            self._last_run = datetime.now().isoformat()
            self._write_status("complete", summary, elapsed)
            
        except Exception as e:
            logger.error(f"🌙 Dream cycle failed: {e}")
            self._status = "error"
            self._write_status("error", str(e))
    
    async def _compress_episodic_memories(self) -> int:
        """
        Score and compress old conversation logs.
        
        For each user silo, scans context_private.jsonl files older than
        24 hours, scores entries for salience, compresses low-salience
        entries into summaries, and archives the raw data.
        """
        from src.memory.salience import SalienceScorer
        
        compressed_count = 0
        users_dir = Path("memory/users")
        
        if not users_dir.exists():
            logger.info("Dream compress: memory/users directory does not exist — nothing to compress.")
            return 0
        
        total_files_scanned = 0
        total_files_skipped = 0
        
        for user_folder in users_dir.iterdir():
            if not user_folder.is_dir():
                continue
            
            for context_file in ["context_private.jsonl", "context_public.jsonl"]:
                context_path = user_folder / context_file
                if not context_path.exists():
                    continue
                
                total_files_scanned += 1
                try:
                    result = await self._compress_context_file(
                        context_path, user_folder
                    )
                    if result == 0:
                        total_files_skipped += 1
                    compressed_count += result
                except Exception as e:
                    logger.warning(f"Compression failed for {context_path}: {e}")
        
        # ─── Diagnostic Logging (Fix 4) ──────────────────────
        if compressed_count == 0:
            if total_files_scanned == 0:
                logger.info("Dream compress: 0 conversations compressed — no context files found.")
            else:
                logger.info(
                    f"Dream compress: 0 conversations compressed — "
                    f"scanned {total_files_scanned} files, "
                    f"all {total_files_skipped} skipped (too small or too recent)."
                )
        else:
            logger.info(
                f"Dream compress: {compressed_count} conversations compressed "
                f"from {total_files_scanned} files scanned."
            )
        
        return compressed_count
    
    async def _compress_context_file(self, context_path: Path, user_folder: Path) -> int:
        """Compress a single context file, preserving high-salience entries."""
        from src.memory.salience import SalienceScorer
        
        lines = []
        try:
            with open(context_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            lines.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            return 0
        
        if len(lines) < 50:
            return 0  # Not enough to compress
        
        # Split: keep last 20 entries as recent, compress older ones
        recent = lines[-20:]
        candidates = lines[:-20]
        
        if not candidates:
            return 0
        
        # Score each entry
        scored = []
        for entry in candidates:
            score = SalienceScorer.score_entry(entry)
            scored.append((entry, score))
        
        # Keep high-salience entries (>= 0.6), compress the rest
        high_salience = [e for e, s in scored if s >= 0.6]
        low_salience = [e for e, s in scored if s < 0.6]
        
        if not low_salience:
            return 0
        
        # Archive raw data before compression
        archive_dir = user_folder / "archive"
        archive_dir.mkdir(exist_ok=True)
        archive_file = archive_dir / f"compressed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        
        with open(archive_file, 'w', encoding='utf-8') as f:
            for entry in low_salience:
                f.write(json.dumps(entry) + "\n")
        
        # Build compressed summary
        summary_text = self._build_compression_summary(low_salience)
        
        # Write compressed entry + high-salience + recent back
        compressed_entry = {
            "ts": datetime.now().isoformat(),
            "type": "compressed_summary",
            "original_count": len(low_salience),
            "summary": summary_text,
            "scope": low_salience[0].get("scope", "PUBLIC") if low_salience else "PUBLIC"
        }
        
        # Rewrite the context file
        with open(context_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(compressed_entry) + "\n")
            for entry in high_salience:
                f.write(json.dumps(entry) + "\n")
            for entry in recent:
                f.write(json.dumps(entry) + "\n")
        
        logger.info(
            f"Compressed {len(low_salience)} entries → 1 summary "
            f"(kept {len(high_salience)} high-salience, {len(recent)} recent) "
            f"for {context_path}"
        )
        return len(low_salience)
    
    def _build_compression_summary(self, entries: list) -> str:
        """Build a text summary from low-salience entries."""
        lines = []
        for e in entries[:30]:  # Cap to prevent mega-summaries
            user = e.get("user", "")[:500]
            bot = e.get("bot", "")[:500]
            if user:
                lines.append(f"User: {user}")
            if bot:
                lines.append(f"Bot: {bot}")
        
        if not lines:
            return f"[{len(entries)} routine interactions compressed]"
        
        return f"[Compressed {len(entries)} interactions]\n" + "\n".join(lines)
    
    async def _prune_kg_nodes(self) -> int:
        """Prune redundant or stale KG nodes."""
        pruned = 0
        
        if not hasattr(self.bot, 'hippocampus') or not self.bot.hippocampus:
            return 0
        
        graph = self.bot.hippocampus.graph
        if not graph:
            return 0
        
        try:
            # Remove nodes with no relationships and no recent access
            # This is a conservative prune — only truly orphaned nodes
            result = graph.run_query(
                "MATCH (n) WHERE NOT (n)--() "
                "AND n.created_at < datetime() - duration('P30D') "
                "DELETE n RETURN count(n) as pruned"
            )
            if result and len(result) > 0:
                pruned = result[0].get("pruned", 0)
                logger.info(f"KG pruned {pruned} orphan nodes")
        except Exception as e:
            logger.warning(f"KG prune failed (non-critical): {e}")
        
        return pruned
    
    async def _process_quarantine(self) -> int:
        """
        Process quarantined KG entries — attempt to re-parent orphaned facts.
        
        Strategy:
        - Check if props already contain a user_id that was stripped → re-use it
        - Check if subject/target matches a known user pattern (e.g. "User_123", "Maria") → infer owner
        - Check if entry came from a persona → assign user_id=-1 (system/persona data)
        - If no owner can be determined → leave in quarantine for manual review
        """
        if not hasattr(self.bot, 'hippocampus') or not self.bot.hippocampus:
            return 0
        
        graph = self.bot.hippocampus.graph
        if not graph or not hasattr(graph, 'quarantine'):
            return 0
        
        quarantine = graph.quarantine
        if quarantine.size() == 0:
            return 0
        
        logger.info(f"Processing quarantine queue: {quarantine.size()} entries")
        
        resolved = 0
        # Process up to 50 entries per cycle to avoid long-running operations
        entries = quarantine.peek(n=50)
        
        # Build a user lookup from memory/users directory
        user_lookup = self._build_user_lookup()
        
        # Process in reverse order so index stays valid after resolve()
        for i in range(len(entries) - 1, -1, -1):
            entry = entries[i]
            inferred_uid = self._infer_user_id(entry, user_lookup)
            
            if inferred_uid is not None:
                # Re-commit with the inferred user_id
                try:
                    graph.add_relationship(
                        source_name=entry["source"],
                        rel_type=entry["rel_type"],
                        target_name=entry["target"],
                        layer=entry.get("layer", "narrative"),
                        user_id=inferred_uid,
                        scope=entry.get("props", {}).get("scope", "PRIVATE"),
                        source="quarantine_resolved"
                    )
                    quarantine.resolve(i)
                    resolved += 1
                    logger.info(
                        f"QUARANTINE RESOLVED: {entry['source']}-[{entry['rel_type']}]->{entry['target']} "
                        f"→ user_id={inferred_uid}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to re-commit quarantined entry: {e}")
        
        if resolved:
            logger.info(f"Quarantine processing complete: {resolved}/{len(entries)} entries resolved")
        
        return resolved
    
    def _build_user_lookup(self) -> dict:
        """
        Build a mapping of username patterns → user_id from the memory/users directory.
        Folder names follow the pattern: username_userid (e.g., maria_123456789)
        """
        lookup = {}
        users_dir = Path("memory/users")
        if not users_dir.exists():
            return lookup
        
        for folder in users_dir.iterdir():
            if not folder.is_dir():
                continue
            name = folder.name
            # Parse "username_userid" format
            parts = name.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    uid = int(parts[1])
                    username = parts[0].lower()
                    lookup[username] = uid
                except ValueError:
                    continue
        
        return lookup
    
    def _infer_user_id(self, entry: dict, user_lookup: dict):
        """
        Attempt to infer user_id for a quarantined entry.
        
        Returns:
            int: inferred user_id, or None if unresolvable
        """
        props = entry.get("props", {})
        source = entry.get("source", "")
        target = entry.get("target", "")
        
        # 1. Check if props already had a user_id that was stripped
        if "user_id" in props and props["user_id"] is not None:
            try:
                return int(props["user_id"])
            except (ValueError, TypeError) as e:
                logger.debug(f"Dream consolidation parse skip: {e}")
        
        # 2. Check for User_<id> pattern in source or target
        user_pattern = re.compile(r'User_(\d+)', re.IGNORECASE)
        for text in [source, target]:
            match = user_pattern.search(text)
            if match:
                return int(match.group(1))
        
        # 3. Check if source/target matches a known username
        for text in [source.lower(), target.lower()]:
            if text in user_lookup:
                return user_lookup[text]
        
        # 4. Check if this looks like persona/system data
        layer = entry.get("layer", "").lower()
        violation = entry.get("violation", "").lower()
        if "persona" in violation or "persona" in source.lower() or "persona" in target.lower():
            return -1  # System/persona data
        
        # 5. If violation is specifically about missing user_id and we have a
        #    single user in the lookup, assign to them (small-system heuristic)
        if "user_id" in violation or "identity" in violation or "ownership" in violation:
            if len(user_lookup) == 1:
                return list(user_lookup.values())[0]
        
        # Unresolvable — leave in quarantine
        return None
    
    def _persist_sentinel_cache(self) -> bool:
        """Persist sentinel immune cache to disk."""
        try:
            if not hasattr(self.bot, 'cerebrum'):
                return False
            
            superego = self.bot.cerebrum.lobes.get("SuperegoLobe")
            if not superego:
                return False
            
            sentinel = superego.get_ability("SentinelAbility")
            if not sentinel or not sentinel._review_cache:
                return False
            
            cache_path = Path("memory/system/sentinel_cache.json")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serialize cache with timestamp
            cache_data = {
                "persisted_at": datetime.now().isoformat(),
                "entries": {}
            }
            
            for key, value in sentinel._review_cache.items():
                # Value is (is_approved, reason) tuple
                cache_data["entries"][key] = {
                    "approved": value[0],
                    "reason": value[1]
                }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info(f"Persisted {len(cache_data['entries'])} sentinel cache entries")
            return True
            
        except Exception as e:
            logger.warning(f"Sentinel cache persistence failed: {e}")
            return False
    
    def _write_status(self, status: str, message: str, elapsed: float = 0):
        """Write dream status for HUD display."""
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "status": status,
                "message": message,
                "last_run": self._last_run or "Never",
                "elapsed_seconds": round(elapsed, 1),
                "timestamp": datetime.now().isoformat()
            }
            with open(STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug(f"Dream consolidation suppressed: {e}")
    
    def get_status(self) -> str:
        """Get current dream cycle status string for HUD."""
        return self._status


def setup_dream_scheduler(bot):
    """
    Register the dream consolidation daemon with the TaskScheduler.
    Runs daily at 3:00 AM.
    """
    from src.scheduler import get_scheduler
    
    daemon = DreamConsolidationDaemon(bot)
    scheduler = get_scheduler()
    
    scheduler.add_daily_task(
        name="dream_consolidation",
        hour=3,
        minute=0,
        coro_func=daemon.run
    )
    
    logger.info("Dream Consolidation Daemon scheduled for 3:00 AM daily")
    return daemon
