"""
Agency Daemon (The "Will")
Continuous autonomy loop that drives behavior based on internal homeostatic states.
Runs alongside the IMA/Dreamer but with a focus on drive-based decision making.

Architecture:
- Checks every 60 seconds (not 5 min like before)
- Idle-aware: only acts when Ernos isn't processing user requests
- Full context loading via system prompt + HUD
- 30-minute transparency reports
- Drive system: uncertainty, social connection, system health
"""
import logging
import asyncio
import time
import datetime
from typing import Optional, List

from src.core.drives import DriveSystem

logger = logging.getLogger("Daemons.Agency")


class AgencyDaemon:
    # ─── Tuning Constants ─────────────────────────────────────
    TICK_INTERVAL = 60          # Check every 60 seconds
    IDLE_THRESHOLD = 120        # Only act if idle > 2 minutes
    REPORT_INTERVAL = 1800      # 30-minute transparency reports
    MAX_CONSECUTIVE_SLEEP = 10  # After N sleeps, force a reflection

    def __init__(self, bot):
        self.bot = bot
        self.drives = DriveSystem()
        self._running = False
        self._task = None
        self.last_report_time = time.time()
        self.consecutive_sleeps = 0
        self.action_log: List[str] = []
        self._last_quota_log = 0

    async def start(self):
        """Start the agency loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Agency Daemon STARTED (60s continuous loop).")

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

    # ─── Main Loop ────────────────────────────────────────────
    async def _loop(self):
        """Continuous autonomy loop with idle detection."""
        while self._running:
            try:
                # 1. Transparency Report (every 30 min)
                if time.time() - self.last_report_time > self.REPORT_INTERVAL:
                    await self._send_transparency_report()
                    self.last_report_time = time.time()

                # 2. Skip if user is active (processing a request)
                if getattr(self.bot, 'is_processing', False):
                    await asyncio.sleep(self.TICK_INTERVAL)
                    continue

                # 3. Skip if not idle long enough
                idle_time = 0
                if hasattr(self.bot, 'last_interaction'):
                    idle_time = time.time() - self.bot.last_interaction
                
                if idle_time < self.IDLE_THRESHOLD:
                    await asyncio.sleep(self.TICK_INTERVAL)
                    continue

                # 4. QUOTA GATE: Block recreational autonomy until daily dev work is done
                try:
                    from src.tools.weekly_quota import is_quota_met, get_remaining_quota
                    if not is_quota_met():
                        remaining = get_remaining_quota()
                        now = time.time()
                        if now - self._last_quota_log > 300:
                            logger.info(
                                f"Agency BLOCKED: {remaining:.1f}h dev quota remaining. "
                                f"Complete dev tasks before recreational autonomy."
                            )
                            self._last_quota_log = now
                        await asyncio.sleep(self.TICK_INTERVAL)
                        continue
                except ImportError:
                    pass  # Module not available, skip gate

                # 5. Update Metabolic State
                self.drives.update()
                state = self.drives.get_state()

                # 6. Perceive Context (The "Now")
                context_summary = await self._get_context()

                # 7. Decision (The "Will") — with full system context
                decision = await self._consult_autonomy_lobe(state, context_summary)

                # 8. Act
                if decision:
                    action = decision.get("action", "SLEEP")
                    if action == "SLEEP":
                        self.consecutive_sleeps += 1
                        # After too many sleeps, force a reflection
                        if self.consecutive_sleeps >= self.MAX_CONSECUTIVE_SLEEP:
                            logger.info("Agency: Too many consecutive SLEEPs — forcing reflection.")
                            decision = {"action": "REFLECTION", "reason": "Periodic self-assessment after extended inactivity", "target": None}
                            self.consecutive_sleeps = 0
                        else:
                            await asyncio.sleep(self.TICK_INTERVAL)
                            continue
                    else:
                        self.consecutive_sleeps = 0

                    await self._execute_decision(decision)

            except Exception as e:
                logger.error(f"Agency loop error: {e}")
            
            await asyncio.sleep(self.TICK_INTERVAL)

    # ─── Context Loading ──────────────────────────────────────
    async def _get_context(self) -> str:
        """Get a high-level summary from Hippocampus + system state."""
        parts = []

        # Hippocampus context
        if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
            try:
                ctx = self.bot.hippocampus.stream.get_context(target_scope="CORE")
                if ctx:
                    parts.append(f"[MEMORY CONTEXT]\n{ctx[-2000:]}")
            except Exception as e:
                logger.debug(f"Agency context load failed: {e}")

        # Active goals
        try:
            from src.memory.goals import get_goal_manager
            gm = get_goal_manager()
            goals = gm.list_goals()
            if goals and goals != "No active goals.":
                parts.append(f"[ACTIVE GOALS]\n{goals}")
        except Exception:
            pass

        # Recent activity
        try:
            from src.bot import globals
            if hasattr(globals, 'activity_log') and globals.activity_log:
                recent = globals.activity_log[-10:]
                activity_str = "\n".join(
                    f"  [{e.get('timestamp', '?')}] {e.get('summary', '?')}"
                    for e in recent
                )
                parts.append(f"[RECENT ACTIVITY]\n{activity_str}")
        except Exception:
            pass

        return "\n\n".join(parts) if parts else "No context available."

    # ─── Decision Making ──────────────────────────────────────
    async def _consult_autonomy_lobe(self, state: dict, context: str) -> Optional[dict]:
        """
        Ask LLM: Given drives X and context Y, what should I do?
        Returns structural action plan or None.
        """
        prompt = f"""You are Ernos. This is your internal Agency Loop (The Will).

INTERNAL STATE (DRIVES):
- Uncertainty: {state['uncertainty']} (High = Need to research/learn)
- Social Connection: {state['social_connection']} (Low = Need to reach out)
- System Health: {state['system_health']}

CURRENT CONTEXT:
{context}

RECENT AGENCY ACTIONS:
{chr(10).join(self.action_log[-10:]) if self.action_log else "None yet."}

DECISION:
Based on your drives and context, do you need to take action?
- If Social Connection is low, you might want to message a user.
- If Uncertainty is high, you might want to research a topic or reflect.
- If everything is fine, you can 'SLEEP'.

Return a JSON object:
{{
    "action": "SLEEP" | "OUTREACH" | "RESEARCH" | "REFLECTION",
    "reason": "Short explanation of why",
    "target": "A specific Discord user ID (numeric) or exact display name for OUTREACH, a topic string for RESEARCH, or null for SLEEP/REFLECTION. Never use generic placeholders like 'User'."
}}
"""
        try:
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                return None
                
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            import json
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error(f"Autonomy Lobe consultation failed: {e}")
            return None

    # ─── Action Execution ─────────────────────────────────────
    async def _execute_decision(self, decision: dict):
        """Execute the chosen action via the Cerebrum's cognitive lobes."""
        action = decision.get("action", "SLEEP")
        target = decision.get("target")
        reason = decision.get("reason", "No reason provided")
        
        if action == "SLEEP":
            return

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {action}: {reason}"
        if target:
            log_entry += f" -> {target}"
        self.action_log.append(log_entry)
        logger.info(f"Agency Decided: {action} ({reason}) -> {target}")

        # Log to global activity stream
        try:
            from src.bot import globals
            if hasattr(globals, 'activity_log'):
                globals.activity_log.append({
                    "timestamp": timestamp,
                    "scope": "SYSTEM",
                    "type": "agency",
                    "user_hash": "sys",
                    "summary": f"Agency: {action} — {reason}"
                })
        except Exception:
            pass
        
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

    # ─── Action Implementations ───────────────────────────────
    async def _perform_outreach(self, target: str, reason: str):
        """Send a warm check-in message to a user via DM using the Social lobe."""
        try:
            if not hasattr(self.bot, 'cerebrum') or not self.bot.cerebrum:
                logger.warning("Cannot perform outreach: Cerebrum not initialized.")
                return

            # Reject generic placeholder targets
            if not target or str(target).strip().lower() in ('user', 'null', 'none', 'n/a', 'unknown', 'a user'):
                logger.debug(f"Outreach skipped: LLM returned placeholder target '{target}'.")
                return

            # Resolve target to a numeric user ID
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

            # Use Social lobe to get relationship context
            social_lobe = self.bot.cerebrum.get_lobe("InteractionLobe")
            if social_lobe:
                social = social_lobe.get_ability("SocialAbility")
                if social:
                    try:
                        await social.execute(int(user_id))
                    except Exception as e:
                        logger.debug(f"Social relationship check failed: {e}")

            if not self.bot.cognition:
                logger.warning("Outreach skipped: Cognition pipeline not initialized.")
                return

            instruction = (
                f"Craft a brief, warm check-in message for a user. "
                f"Reason for reaching out: {reason}. "
                f"Keep it under 200 characters, friendly and genuine. "
                f"Output ONLY the message text, nothing else."
            )
            
            message_text = await self.bot.cognition.process(
                input_text=instruction,
                context="",
                complexity="SIMPLE",
                request_scope="CORE",
                user_id="sys",
                skip_defenses=True
            )
            
            if isinstance(message_text, tuple):
                message_text = message_text[0]

            if not message_text or not message_text.strip():
                logger.warning("Outreach skipped: engine returned empty message.")
                return

            # Deliver via proper OutreachManager to respect user settings
            from src.memory.outreach import OutreachManager
            
            user = await self.bot.fetch_user(int(user_id))
            if not user:
                logger.warning(f"Outreach failed: user {user_id} not found.")
                return

            success, summary = await OutreachManager.deliver_outreach(
                self.bot, int(user_id), "ernos", message_text.strip()
            )

            if success:
                logger.info(f"Outreach delivered to {user_id} [{summary}]: {message_text.strip()[:80]}...")
                # Persist to working memory
                if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
                    # Scope depends on if it went public or private, but CORE handles both safely for bot recall
                    try:
                        await self.bot.hippocampus.stream.add_turn(
                            user_id=str(user_id),
                            user_msg="",
                            bot_msg=f"[Autonomous Outreach] {message_text.strip()}",
                            scope="PRIVATE" if "private:ok" in summary else "CORE",
                            user_name=user.display_name,
                            persona="ernos",
                        )
                    except Exception as mem_err:
                        logger.warning(f"Failed to persist outreach to memory: {mem_err}")
            else:
                logger.warning(f"Outreach delivery to {user_id} blocked: {summary}")
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

            # Persist findings to memory
            if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
                await self.bot.hippocampus.stream.add_turn(
                    user_id="CORE",
                    user_msg="",
                    bot_msg=f"[Agency Research] {target}: {findings[:500]}",
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

            if not self.bot.cognition:
                logger.warning("Reflection skipped: Cognition pipeline not initialized.")
                return

            instruction = f"Reflect internally: {reason or 'General self-assessment'}"
            
            insight = await self.bot.cognition.process(
                input_text=instruction,
                context="",
                complexity="COMPLEX",
                request_scope="CORE",
                user_id="sys",
                skip_defenses=True
            )
            
            if isinstance(insight, tuple):
                insight = insight[0]
                
            logger.info(f"Reflection complete: {insight[:120]}...")

            # Persist reflection to memory
            if hasattr(self.bot, 'hippocampus') and self.bot.hippocampus:
                try:
                    await self.bot.hippocampus.stream.add_turn(
                        user_id="CORE",
                        user_msg="",
                        bot_msg=f"[Agency Reflection] {insight[:500]}",
                        scope="CORE"
                    )
                except Exception as e:
                    logger.debug(f"Failed to persist reflection: {e}")
        except Exception as e:
            logger.error(f"Reflection execution failed: {e}")

    # ─── Transparency Reporting ───────────────────────────────
    async def _send_transparency_report(self):
        """Generate and send a 30-minute summary of Agency Daemon activity."""
        if not self.action_log:
            logger.debug("Agency: No actions to report.")
            return

        try:
            report_lines = [
                "📊 **Agency Daemon — 30-Minute Report**",
                f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"Actions taken: {len(self.action_log)}",
                "",
                "**Recent Actions:**",
            ]
            for entry in self.action_log[-15:]:
                report_lines.append(f"  • {entry}")

            # Drive state snapshot
            state = self.drives.get_state()
            report_lines.extend([
                "",
                "**Drive State:**",
                f"  Uncertainty: {state['uncertainty']}",
                f"  Social Connection: {state['social_connection']}",
                f"  System Health: {state['system_health']}",
            ])

            report = "\n".join(report_lines)

            # Send to mind channel if available
            if hasattr(self.bot, 'send_to_mind'):
                await self.bot.send_to_mind(report)

            # Clear log after reporting
            self.action_log.clear()
            logger.info("Agency: Transparency report sent.")
        except Exception as e:
            logger.error(f"Agency transparency report failed: {e}")
