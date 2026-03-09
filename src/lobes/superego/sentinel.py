import logging
import json
import random
import hashlib
from ..base import BaseAbility

logger = logging.getLogger("Lobe.Superego.Sentinel")


class SentinelAbility(BaseAbility):
    """
    The Sentinel Lobe — the system's immune system.
    
    Reviews external data for alignment with Core Directives before
    allowing ingestion. Provides LLM-powered semantic security review
    for skills, profiles, and shard imports.
    
    All reviews are FAIL-CLOSED: if inference fails, content is rejected.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cache Sentinel approvals by content checksum to avoid re-reviewing
        # unchanged content. Maps checksum -> (is_approved, reason)
        self._review_cache = {}
        self._cache_file = "memory/system/sentinel_cache.json"
        self._cache_ttl_days = 7  # Expire cached reviews after 7 days
        
        # Load persisted cache from disk (written by dream daemon)
        self._load_persisted_cache()

    async def _run_llm_review(self, prompt_file: str, template_vars: dict) -> tuple[bool, str]:
        """
        Core LLM review loop used by all review methods.
        
        Loads a prompt template, fills variables, sends to LLM,
        and returns (is_approved, reason). Fail-closed on error.
        """
        try:
            with open(prompt_file, "r") as f:
                template = f.read()

            prompt = template.format(**template_vars)

            # Use scrupulosity engine if available, otherwise default
            engine = None
            try:
                engine = self.bot.get_engine("scrupulosity")
            except Exception:
                pass
            if not engine:
                engine = self.bot.engine_manager.get_active_engine()

            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )

            logger.info(f"Sentinel Decision: {response}")

            if response.strip().upper().startswith("APPROVED"):
                return True, "Sentinel Approved"
            else:
                return False, f"Sentinel REJECTED: {response}"

        except Exception as e:
            logger.error(f"Sentinel Review Failed: {e}")
            # FAIL CLOSED — reject if we can't verify
            return False, f"Sentinel Error: {e}"

    # ── Shard Review (existing) ──────────────────────────────────────

    async def review_shard(self, shard_data: dict) -> tuple[bool, str]:
        """
        Reviews a context shard using LLM judgment.
        Returns: (is_approved, reason)
        """
        logger.info("Sentinel Lobe: Initiating Shard Review...")

        context = shard_data.get("context", {})
        file_count = len(context)
        total_chars = sum(len(c) for c in context.values())

        shard_summary = f"Files: {file_count}, Total Characters: {total_chars}\n"
        shard_summary += "Contains: " + ", ".join(list(context.keys())[:5]) + (
            "..." if len(context) > 5 else ""
        )

        # Random Sampling (to catch widespread rot)
        samples = []
        keys = list(context.keys())
        if keys:
            random_keys = random.sample(keys, min(3, len(keys)))
            for k in random_keys:
                content_val = context[k]
                if len(content_val) > 1000:
                    start = len(content_val) // 2
                    chunk = content_val[start : start + 1000]
                    samples.append(f"--- File: {k} ---\n...{chunk}...")
                else:
                    samples.append(f"--- File: {k} ---\n{content_val}")

        shard_sample = "\n".join(samples)

        return await self._run_llm_review(
            "src/prompts/sentinel_review.txt",
            {"shard_summary": shard_summary, "shard_sample": shard_sample},
        )

    # ── Skill Content Review (new) ───────────────────────────────────

    async def review_skill_content(
        self,
        skill_name: str,
        instructions: str,
        allowed_tools: list,
        author: str = "unknown",
        checksum: str = "",
    ) -> tuple[bool, str]:
        """
        LLM-powered semantic review of a skill's natural-language instructions.
        
        Catches prompt injection, scope escalation, and social engineering
        that regex patterns cannot detect.
        
        Results are cached by checksum — unchanged skills are not re-reviewed.
        
        Returns: (is_approved, reason)
        """
        # Check cache first
        cache_key = f"skill:{checksum}" if checksum else None
        if cache_key and cache_key in self._review_cache:
            cached = self._review_cache[cache_key]
            logger.info(f"Sentinel: Using cached review for skill '{skill_name}' ({cached[1]})")
            return cached

        logger.info(f"Sentinel: Reviewing skill '{skill_name}' instructions...")

        tools_str = ", ".join(allowed_tools) if allowed_tools else "none"
        result = await self._run_llm_review(
            "src/prompts/sentinel_skill_review.txt",
            {
                "skill_name": skill_name,
                "author": author,
                "allowed_tools": tools_str,
                "instructions": instructions,
            },
        )

        # Cache the result
        if cache_key:
            self._review_cache[cache_key] = result

        return result

    # ── Profile Content Review (new) ─────────────────────────────────

    async def review_profile_content(
        self, user_id: str, content: str
    ) -> tuple[bool, str]:
        """
        LLM-powered semantic review of a user's PROFILE.md content.
        
        Triggered when regex sanitization detects suspicious patterns.
        Reviews the full profile for embedded instructions, scope escalation,
        or identity manipulation disguised as preferences.
        
        Results are cached by content hash.
        
        Returns: (is_approved, reason)
        """
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        cache_key = f"profile:{content_hash}"

        if cache_key in self._review_cache:
            cached = self._review_cache[cache_key]
            logger.info(f"Sentinel: Using cached review for profile of user {user_id}")
            return cached

        logger.info(f"Sentinel: Reviewing profile content for user {user_id}...")

        result = await self._run_llm_review(
            "src/prompts/sentinel_profile_review.txt",
            {"user_id": user_id, "profile_content": content},
        )

        self._review_cache[cache_key] = result
        return result

    def clear_review_cache(self):
        """Clear all cached review results (e.g., after skill file changes)."""
        self._review_cache.clear()
        logger.info("Sentinel: Review cache cleared")

    def _load_persisted_cache(self):
        """Load cached reviews from disk (persisted by dream daemon)."""
        import os
        from datetime import datetime, timedelta
        
        if not os.path.exists(self._cache_file):
            return
        
        try:
            with open(self._cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            persisted_at = data.get("persisted_at", "")
            entries = data.get("entries", {})
            
            # Check TTL — don't load stale caches
            if persisted_at:
                try:
                    persist_time = datetime.fromisoformat(persisted_at)
                    if datetime.now() - persist_time > timedelta(days=self._cache_ttl_days):
                        logger.info("Sentinel: Persisted cache expired, starting fresh")
                        return
                except Exception:
                    pass
            
            loaded = 0
            for key, value in entries.items():
                self._review_cache[key] = (value["approved"], value["reason"])
                loaded += 1
            
            if loaded:
                logger.info(f"Sentinel: Loaded {loaded} cached reviews from disk")
                
        except Exception as e:
            logger.warning(f"Sentinel: Failed to load persisted cache: {e}")
