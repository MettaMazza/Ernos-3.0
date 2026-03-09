"""
Agency Daemon (The "Will")
Autonomous loop that drives behavior based on internal homeostatic states.
"""
import logging
import asyncio
from datetime import datetime
from typing import Optional

from src.core.drives import DriveSystem

logger = logging.getLogger("Daemons.Agency")

class AgencyDaemon:
    # Loop frequency in seconds
    TICK_INTERVAL = 300  # Check every 5 minutes

    def __init__(self, bot):
        self.bot = bot
        self.drives = DriveSystem()
        self._running = False
        self._task = None

    async def start(self):
        """Start the agency loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Agency Daemon STARTED.")

    async def stop(self):
        """Stop the agency loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Agency Daemon STOPPED.")

    async def _loop(self):
        """Main autonomy loop."""
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Agency loop error: {e}")
            
            await asyncio.sleep(self.TICK_INTERVAL)

    async def _tick(self):
        """Single decision cycle."""
        # 0. QUOTA GATE: Block recreational autonomy until daily dev work is done
        try:
            from src.tools.weekly_quota import is_quota_met, get_remaining_quota
            if not is_quota_met():
                remaining = get_remaining_quota()
                # Only log once per 5 minutes to avoid spam
                import time as _time
                last_log = getattr(self, '_last_quota_log', 0)
                if _time.time() - last_log > 300:
                    logger.info(f"Agency BLOCKED: {remaining:.1f}h dev quota remaining. "
                                f"Complete dev tasks before recreational autonomy.")
                    self._last_quota_log = _time.time()
                return  # Skip this tick — no recreational activity until quota met
        except ImportError:
            pass  # Module not available, skip gate

        # 1. Update Metabolic State
        self.drives.update()
        state = self.drives.get_state()
        
        # 2. Perceive Context (The "Now")
        # Get a high-level summary from Hippocampus
        context_summary = "No context available."
        if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
             # Use public scope to get general "world state"
             ctx = self.bot.hippocampus.stream.get_context(target_scope="CORE")
             # Truncate for prompt efficiency
             context_summary = ctx[-2000:] if ctx else "Silence."

        # 3. Decision (The "Will")
        # Ask the Autonomy Lobe (LLM) what to do
        decision = await self._consult_autonomy_lobe(state, context_summary)
        
        # 4. Act
        if decision:
            await self._execute_decision(decision)

    async def _consult_autonomy_lobe(self, state: dict, context: str) -> Optional[dict]:
        """
        Ask LLM: Given drives X and context Y, what should I do?
        Returns structural action plan or None.
        """
        prompt = f"""You are Ernos. This is your internal Agency Loop.
        
INTERNAL STATE (DRIVES):
- Uncertainty: {state['uncertainty']} (High = Need to research/learn)
- Social Connection: {state['social_connection']} (Low = Need to reach out)
- System Health: {state['system_health']}

CURRENT CONTEXT:
{context}

DECISION:
Based on your drives and context, do you need to take action?
- If Social Connection is low, you might want to message a user.
- If Uncertainty is high, you might want to research a topic or reflect.
- If everything is fine, you can 'SLEEP'.

Return a JSON object:
{{
    "action": "SLEEP" | "OUTREACH" | "RESEARCH" | "REFLECTION",
    "reason": "Short explanation of why",
    "target": "User ID, Topic, or null"
}}
"""
        try:
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                return None
                
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            # Simple JSON parsing (robustness needed in prod)
            import json
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error(f"Autonomy Lobe consultation failed: {e}")
            return None

    async def _execute_decision(self, decision: dict):
        """Execute the chosen action via the Cerebrum's cognitive lobes."""
        action = decision.get("action", "SLEEP")
        target = decision.get("target")
        reason = decision.get("reason")
        
        if action == "SLEEP":
            return

        logger.info(f"Agency Decided: {action} ({reason}) -> {target}")
        
        if action == "OUTREACH":
            self.drives.modify_drive("social_connection", 10.0)
            if target:
                await self._perform_outreach(target, reason)

        elif action == "RESEARCH":
            self.drives.modify_drive("uncertainty", -5.0)
            if target:
                await self._perform_research(target, reason)
        
        elif action == "REFLECTION":
            self.drives.modify_drive("uncertainty", -2.0)
            await self._perform_reflection(reason)

    async def _perform_outreach(self, target: str, reason: str):
        """Send a warm check-in message to a user via DM using the Social lobe."""
        try:
            if not hasattr(self.bot, 'cerebrum') or not self.bot.cerebrum:
                logger.warning("Cannot perform outreach: Cerebrum not initialized.")
                return

            # ── Resolve target to a numeric user ID ──────────────
            user_id = ''.join(filter(str.isdigit, str(target)))

            # If no digits found, try to resolve by display name from guild members
            if not user_id:
                for guild in self.bot.guilds:
                    for member in guild.members:
                        if member.display_name.lower() == str(target).lower() or \
                           member.name.lower() == str(target).lower():
                            user_id = str(member.id)
                            break
                    if user_id:
                        break

            if not user_id:
                logger.warning(f"Outreach skipped: could not resolve user ID from '{target}'.")
                return

            # ── Use Social lobe to get relationship context ──────
            social_lobe = self.bot.cerebrum.get_lobe("InteractionLobe")
            if social_lobe:
                social = social_lobe.get_ability("SocialAbility")
                if social:
                    try:
                        await social.execute(int(user_id))
                    except Exception as e:
                        logger.debug(f"Social relationship check failed: {e}")

            # ── Craft outreach message via engine ────────────────
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                logger.warning("Outreach skipped: no active engine.")
                return

            instruction = (
                f"Craft a brief, warm check-in message for a user. "
                f"Reason for reaching out: {reason}. "
                f"Keep it under 200 characters, friendly and genuine. "
                f"Output ONLY the message text, nothing else."
            )
            message_text = await self.bot.loop.run_in_executor(
                None, engine.generate_response, instruction
            )

            if not message_text or not message_text.strip():
                logger.warning("Outreach skipped: engine returned empty message.")
                return

            # ── Send as DM ───────────────────────────────────────
            user = await self.bot.fetch_user(int(user_id))
            if user:
                await user.send(message_text.strip())
                logger.info(f"Outreach sent to {user_id}: {message_text.strip()[:80]}...")

                # ── Persist to working memory so Ernos can recall what he said ──
                if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
                    try:
                        await self.bot.hippocampus.stream.add_turn(
                            user_id=str(user_id),
                            user_msg="",
                            bot_msg=f"[Autonomous Outreach] {message_text.strip()}",
                            scope="PRIVATE",
                            user_name=user.display_name,
                            persona="ernos",
                        )
                        logger.info(f"Outreach message persisted to working memory for user {user_id}")
                    except Exception as mem_err:
                        logger.warning(f"Failed to persist outreach to memory: {mem_err}")
            else:
                logger.warning(f"Outreach failed: user {user_id} not found.")
        except Exception as e:
            logger.error(f"Outreach execution failed: {e}")

    async def _perform_research(self, target: str, reason: str):
        """Research a topic using the World/Research lobe and log findings."""
        try:
            if not hasattr(self.bot, 'cerebrum') or not self.bot.cerebrum:
                logger.warning("Cannot perform research: Cerebrum not initialized.")
                return

            instruction = f"Research: {target}. Motivation: {reason}"
            interaction_lobe = self.bot.cerebrum.get_lobe("InteractionLobe")
            if not interaction_lobe:
                logger.warning("Research skipped: InteractionLobe not initialized.")
                return
            research = interaction_lobe.get_ability("ResearchAbility")
            if not research:
                logger.warning("Research skipped: ResearchAbility not available.")
                return
            findings = await research.execute(instruction)
            logger.info(f"Research on '{target}' complete ({len(findings)} chars).")

            # Persist findings to the knowledge graph if available
            if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
                self.bot.hippocampus.stream.add_turn(
                    role="system",
                    content=f"[Agency Research] {target}: {findings[:500]}",
                    scope="CORE"
                )
        except Exception as e:
            logger.error(f"Research execution failed: {e}")

    async def _perform_reflection(self, reason: str):
        """Deep introspection via the IMA (Internal Monologue Agent) lobe."""
        try:
            if not hasattr(self.bot, 'cerebrum') or not self.bot.cerebrum:
                logger.warning("Cannot perform reflection: Cerebrum not initialized.")
                return

            instruction = f"Reflect internally: {reason or 'General self-assessment'}"
            meta_lobe = self.bot.cerebrum.get_lobe("MetaLobe")
            if not meta_lobe:
                logger.warning("Reflection skipped: MetaLobe not initialized.")
                return
            ima = meta_lobe.get_ability("IntrospectionAbility")
            if not ima:
                logger.warning("Reflection skipped: IntrospectionAbility not available.")
                return
            insight = await ima.execute(instruction)
            logger.info(f"Reflection complete: {insight[:120]}...")
        except Exception as e:
            logger.error(f"Reflection execution failed: {e}")

