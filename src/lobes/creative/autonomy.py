from ..base import BaseAbility
import logging
import asyncio
from config import settings
import time
import re
from src.tools.registry import ToolRegistry
import os
import datetime
import discord
from pathlib import Path

logger = logging.getLogger("Lobe.Creative.Autonomy")

class AutonomyAbility(BaseAbility):
    """
    Autonomy Agent - The conscious thought stream and autonomous action loop.
    The conscious thought stream and autonomous action loop.
    """
    def __init__(self, lobe):
        super().__init__(lobe)
        self.is_running = False
        self.last_summary_time = time.time()
        self.autonomy_log_buffer = [] 
        self.summary_channel_id = 1468579019766366280

    async def execute(self, instruction: str = None) -> str:
        """
        Start the autonomy loop OR perform a one-shot dream/introspection.
        """
        if instruction:
            return await self._one_shot_dream(instruction)

        if self.is_running:
            return "Autonomy Loop already active."
        
        self.is_running = True
        self.last_summary_time = time.time()
        
        logger.info("Autonomy Loop STARTED (T-45s to Idle)")
        logger.critical("Autonomy Loop STARTED (Continuous Entity Mode).")
        
        try:
            while self.is_running:
                await asyncio.sleep(10) # Check every 10s
                
                # 0. 30-Minute Transparency Report
                if time.time() - self.last_summary_time > 1800:
                    await self._send_transparency_report()
                    self.last_summary_time = time.time()

                # Check idle
                if getattr(self.bot, 'is_processing', False):
                    # logger.debug("IMA: User active (Processing). Waiting...")
                    continue
                    
                if hasattr(self.bot, 'last_interaction'):
                    idle_time = time.time() - self.bot.last_interaction
                    # Reduce from 180s to 45s for responsiveness
                    if idle_time > 45:
                        # QUOTA GATE: Check if dev work is needed
                        quota_met = True
                        remaining_hours = 0.0
                        try:
                            from src.tools.weekly_quota import is_quota_met, get_remaining_quota
                            quota_met = is_quota_met()
                            if not quota_met:
                                remaining_hours = get_remaining_quota()
                                # Throttle logging: only log every 5 minutes
                                now = time.time()
                                last_block_log = getattr(self, '_last_block_log', 0)
                                if now - last_block_log > 300:
                                    logger.info(f"IMA: Quota unmet — {remaining_hours:.1f}h remaining. Entering WORK MODE.")
                                    self._last_block_log = now
                        except ImportError:
                            pass  # Module not available, skip gate

                        if not quota_met:
                            # WORK MODE: Drive Ernos to do dev work instead of recreation
                            # Skip in Lite Mode — codebase is retired
                            if getattr(settings, 'AUTONOMY_LITE_MODE', False):
                                logger.debug("IMA: Lite mode — skipping dev work cycle")
                            else:
                                try:
                                    await self._run_dev_work_cycle(remaining_hours)
                                except Exception as e:
                                    logger.error(f"Dev work cycle failed: {e}")
                            # Back off — don't check again for 2 minutes
                            self.bot.last_interaction = time.time() - 100
                            await asyncio.sleep(120)
                            continue

                        logger.info(f"IMA: Detected Idle ({int(idle_time)}s). Triggering Autonomy...")
                        
                        # LOG TO GLOBAL STREAM
                        from src.bot import globals
                        if hasattr(globals, 'activity_log'):
                            ts = datetime.datetime.now().strftime("%H:%M:%S")
                            entry = {
                                "timestamp": ts,
                                "scope": "SYSTEM",
                                "type": "autonomy",
                                "user_hash": "sys",
                                "summary": f"Autonomy Cycle: Idle {int(idle_time)}s. Dreaming..."
                            }
                            globals.activity_log.append(entry)
                        
                        # TRIGGER AUTONOMY LOGIC
                        try:
                            dream_prompt = self._build_dream_prompt()
                            engine = self.bot.engine_manager.get_active_engine()
                            
                            context_history = ""
                            MAX_CONTEXT_HISTORY_CHARS = 8000  # Prevent context from starving generation budget
                            step = 0
                            from collections import defaultdict
                            tool_usage_counts = defaultdict(int)
                            
                            while True: # Uncapped Autonomy
                                # Interrupt if user is active
                                if getattr(self.bot, 'is_processing', False):
                                    logger.info("IMA: User active. Interrupting autonomy.")
                                    break
                                
                                # Hard Step Limit (Safety)
                                if step > 10:
                                    logger.info("IMA: Hard step limit reached (10). Ending cycle.")
                                    break
                                
                                # Generate Thought
                                response = await self.bot.loop.run_in_executor(
                                    None, 
                                    engine.generate_response, 
                                    dream_prompt, 
                                    context_history
                                )
                                
                                # Handle Engine Failure
                                if not response:
                                    logger.warning("IMA: Engine returned None. Stopping.")
                                    break
                                
                                # Buffer for 30m Report
                                self.autonomy_log_buffer.append(f"[{datetime.datetime.now().strftime('%H:%M')}] STEP {step}: {response[:150]}...")

                                # Parse Tools
                                tool_regex_str = r"\[TOOL:\s*(\w+)\((.*?)\)\]"
                                tool_pattern = re.compile(tool_regex_str, re.DOTALL)
                                tool_matches = tool_pattern.findall(response)
                                


                                # Execute Tools
                                context_history += f"\n[STEP {step} THOUGHT]: {response}"
                                
                                # Trim context_history to prevent starving the LLM's generation budget
                                if len(context_history) > MAX_CONTEXT_HISTORY_CHARS:
                                    # Keep the most recent portion
                                    context_history = "[...earlier steps trimmed...]\n" + context_history[-MAX_CONTEXT_HISTORY_CHARS:]
                                
                                # Pure Thought Loop Breaker
                                if not tool_matches and step >= 4:
                                    logger.info("IMA: Pure thought loop limit reached (4 steps). Ending.")
                                    break
                                
                                for tool_name, args_str in tool_matches:
                                    try:
                                        logger.info(f"IMA Executing Tool: {tool_name}")
                                        
                                        # LIMIT CHECK
                                        if tool_name == "add_reaction":
                                            if tool_usage_counts[tool_name] >= 3:
                                                context_history += f"\n[TOOL RESULT {tool_name}]: Blocked (Limit Reached)"
                                                continue
                                            tool_usage_counts[tool_name] += 1

                                        # ROBUST ARGUMENT PARSING (quote-aware)
                                        import json
                                        kwargs = {}
                                        # Sanitize smart/curly quotes from LLM output
                                        args_str = args_str.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
                                        try:
                                            # Try JSON parsing first (handles multi-line)
                                            json_match = re.search(r'\{.*\}', args_str, re.DOTALL)
                                            if json_match:
                                                raw_json = json_match.group()
                                                # Try strict JSON first
                                                try:
                                                    kwargs = json.loads(raw_json)
                                                except json.JSONDecodeError:
                                                    # Normalize LLM-style JSON: single quotes, trailing commas
                                                    import ast
                                                    try:
                                                        kwargs = ast.literal_eval(raw_json)
                                                    except (ValueError, SyntaxError):
                                                        raise  # Fall through to kv_pattern parser
                                            else:
                                                # Parse Python-style kwargs, preserving commas inside quotes
                                                # Matches: key='value with, commas' or key="value"
                                                kv_pattern = re.compile(
                                                    r"(\w+)\s*=\s*"
                                                    r"(?:"
                                                    r"'((?:[^'\\]|\\.)*)'"
                                                    r"|\"((?:[^\"\\]|\\.)*)\""
                                                    r"|([^,\)]+)"
                                                    r")"
                                                )
                                                for m in kv_pattern.finditer(args_str):
                                                    key = m.group(1)
                                                    val = m.group(2) if m.group(2) is not None else (
                                                        m.group(3) if m.group(3) is not None else m.group(4).strip()
                                                    )
                                                    kwargs[key] = val
                                        except Exception as parse_err:
                                            logger.warning(f"Argument parsing failed for {tool_name}: {parse_err}")
                                            kwargs = {}
                                        
                                        # GRACEFUL FALLBACK: Pass raw args_str as raw_input for tools to decode
                                        if not kwargs and args_str.strip():
                                            kwargs["raw_input"] = args_str.strip()
                                        if tool_name == "extract_wisdom":
                                            # Special Internal Tool - extract with fallbacks
                                            insight = kwargs.get("insight", "")
                                            topic = kwargs.get("topic", "General")
                                            
                                            # If kwargs parsing failed, try to extract from raw args_str
                                            if not insight and args_str:
                                                # Match: insight='...', insight="...", "insight": "..."
                                                insight_match = re.search(r'["\']?insight["\']?\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
                                                if insight_match:
                                                    insight = insight_match.group(1)
                                                topic_match = re.search(r'["\']?topic["\']?\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
                                                if topic_match:
                                                    topic = topic_match.group(1)
                                            
                                            # Skip if still no insight
                                            if not insight:
                                                logger.warning(f"extract_wisdom called without insight, skipping. Raw args: {args_str[:100]}")
                                                context_history += f"\n[TOOL RESULT extract_wisdom]: Skipped (no insight provided)"
                                                continue
                                                
                                            result = await self._extract_wisdom(topic, insight)
                                            context_history += f"\n[TOOL RESULT extract_wisdom]: Wisdom Saved: {result}"
                                            self.autonomy_log_buffer.append(f"[WISDOM]: {topic} - {insight}")
                                        elif tool_name == "set_goal":
                                            # Goal setting from autonomy — rate limited
                                            from src.memory.goals import get_goal_manager
                                            import time as _time
                                            last_goal_time = getattr(self, '_last_goal_time', 0)
                                            if _time.time() - last_goal_time < 600:
                                                context_history += f"\n[TOOL RESULT set_goal]: Skipped (cooldown — last goal set {int(_time.time() - last_goal_time)}s ago)"
                                                continue
                                            gm = get_goal_manager()
                                            desc = kwargs.get("description", kwargs.get("raw_input", ""))
                                            priority = int(kwargs.get("priority", 3))
                                            if desc and not gm.is_duplicate(desc):
                                                result = gm.add_goal(desc, priority=priority)
                                                context_history += f"\n[TOOL RESULT set_goal]: {result}"
                                                if "✅" in result:
                                                    self._last_goal_time = _time.time()
                                            else:
                                                context_history += f"\n[TOOL RESULT set_goal]: Skipped (duplicate or empty)"
                                        elif tool_name == "complete_goal":
                                            from src.memory.goals import get_goal_manager
                                            gm = get_goal_manager()
                                            goal_id = kwargs.get("goal_id", kwargs.get("raw_input", ""))
                                            result = gm.complete_goal(goal_id)
                                            context_history += f"\n[TOOL RESULT complete_goal]: {result}"
                                        elif tool_name == "review_goals":
                                            from src.memory.goals import get_goal_manager
                                            gm = get_goal_manager()
                                            result = gm.list_goals()
                                            context_history += f"\n[TOOL RESULT review_goals]: {result}"
                                        elif tool_name == "generate_image":
                                            img_prompt = kwargs.get("prompt", kwargs.get("raw_input", ""))
                                            # Ensure intention is captured
                                            img_intention = kwargs.get("intention", "Autonomous Creation")
                                            
                                            if img_prompt:
                                                kwargs["prompt"] = img_prompt
                                                kwargs["intention"] = img_intention
                                            
                                            # Artist handles channel routing via is_autonomy flag
                                            result = await ToolRegistry.execute(
                                                tool_name, 
                                                user_id="CORE", 
                                                request_scope="CORE",
                                                is_autonomy=True,
                                                **kwargs
                                            )
                                            context_history += f"\n[TOOL RESULT {tool_name}]: {result}"
                                        elif tool_name in ["search_web", "browse_site", "start_deep_research", "consult_science_lobe", "check_world_news"]:
                                            # Throttle search_web to avoid Brave 429 rate limits
                                            if tool_name == "search_web":
                                                import time as _time
                                                last_search = getattr(self, '_last_search_time', 0)
                                                if _time.time() - last_search < 30:
                                                    context_history += f"\n[TOOL RESULT {tool_name}]: Skipped (search cooldown — try again in {30 - int(_time.time() - last_search)}s)"
                                                    continue
                                                self._last_search_time = _time.time()
                                            result = await ToolRegistry.execute(
                                                tool_name, 
                                                user_id="CORE", 
                                                request_scope="CORE",
                                                is_autonomy=True,
                                                **kwargs
                                            )
                                            context_history += f"\n[TOOL RESULT {tool_name}]: {result}"
                                        else:
                                            result = await ToolRegistry.execute(
                                                tool_name, 
                                                user_id="CORE", 
                                                request_scope="CORE", 
                                                **kwargs
                                            )
                                            context_history += f"\n[TOOL RESULT {tool_name}]: {result}"

                                    except Exception as e:
                                        logger.error(f"Tool execution error {tool_name}: {e}")
                                        context_history += f"\n[TOOL ERROR {tool_name}]: {e}"
                                        logger.error(f"IMA Tool Error: {e}")
                                
                                # Persist Step to Core Memory
                                await self.bot.hippocampus.observe(
                                    user_id="CORE",
                                    user_message=f"[AUTONOMY STEP {step}]",
                                    bot_message=response,
                                    channel_id=0,
                                    is_dm=False
                                )
                                
                                # STREAM TO MIND CHANNEL
                                if hasattr(self.bot, 'send_to_mind'):
                                    await self.bot.send_to_mind(f"**[AUTONOMY STEP {step}]**\n{response}")

                                step += 1
                                await asyncio.sleep(2)  # Brief pause between steps
                        
                        except Exception as e:
                            logger.error(f"Dream Cycle Failed: {e}")
                        
                        # ── Continuous Crawler ─────────────────
                        # Run one crawl cycle after each dream cycle
                        # Skip in Lite Mode — reduces overhead
                        if not getattr(settings, 'AUTONOMY_LITE_MODE', False):
                            try:
                                from scripts.continuous_crawler import get_crawler
                                # Use the bot's existing KG connection (hippocampus.graph)
                                kg = getattr(self.bot.hippocampus, 'graph', None) if hasattr(self.bot, 'hippocampus') else None
                                if kg is None:
                                    logger.warning("Crawler: No KG found on bot.hippocampus.graph — will run dry")
                                crawler = get_crawler(kg=kg)
                                crawl_result = await self.bot.loop.run_in_executor(
                                    None, crawler.crawl_cycle
                                )
                                if crawl_result and not crawl_result.get("skipped"):
                                    src = crawl_result.get("source", "?")
                                    new = crawl_result.get("new", 0)
                                    logger.info(f"🕷️ Crawler cycle: {src} → {new} new facts")
                                    if hasattr(self.bot, 'send_to_mind') and new > 0:
                                        await self.bot.send_to_mind(
                                            f"🕷️ **Knowledge Crawler** [{src}]: Ingested {new} new facts"
                                        )
                            except Exception as e:
                                logger.debug(f"Crawler cycle skipped: {e}")
                    
                    # Debounce: Update last interaction to prevent spamming
                    self.bot.last_interaction = time.time() - 100  # Allow re-trigger in ~80s if still idle
                    
        except asyncio.CancelledError:
            self.is_running = False
            logger.info("IMA Loop Cancelled.")
        except Exception as e:
            logger.critical(f"FATAL DREAMER ERROR: {e}. Restarting loop in 10s...")
            self.is_running = False

    async def _run_dev_work_cycle(self, remaining_hours: float):
        """
        WORK MODE: When quota isn't met, drive Ernos to do real dev work.
        Uses the same LLM engine and context-enrichment pattern as the dream loop.
        """
        logger.info(f"IMA WORK MODE: Starting dev cycle ({remaining_hours:.1f}h remaining)")

        dev_prompt = self._build_dev_prompt(remaining_hours)

        try:
            engine = self.bot.engine_manager.get_active_engine()
            context_history = ""
            MAX_CONTEXT_HISTORY_CHARS = 8000

            # Load kernel system prompt — same as cognition pipeline
            # cognition.py passes system_context as 3rd arg to engine.generate_response
            system_prompt = None
            try:
                from src.prompts.manager import PromptManager
                pm = PromptManager()
                system_prompt = pm.get_system_prompt(
                    scope="CORE",
                    is_core=True,
                    active_engine=engine.name if engine else "Unknown",
                )
            except Exception as e:
                logger.warning(f"IMA WORK MODE: Failed to load system prompt: {e}")
            
            # Broadcast cycle start to dev channel
            if hasattr(self.bot, 'send_to_dev_channel'):
                await self.bot.send_to_dev_channel(
                    f"🔧 **WORK MODE ACTIVATED**\n"
                    f"Remaining quota: **{remaining_hours:.1f}h**\n"
                    f"Starting autonomous dev cycle..."
                )
            
            for step in range(5):  # Max 5 dev steps per cycle
                if getattr(self.bot, 'is_processing', False):
                    logger.info("IMA WORK MODE: User active, pausing dev cycle.")
                    if hasattr(self.bot, 'send_to_dev_channel'):
                        await self.bot.send_to_dev_channel("⏸️ **WORK MODE PAUSED** — User is active.")
                    break

                # Generate response — SAME PATTERN AS COGNITION PIPELINE (cognition.py line 142-149)
                # engine.generate_response(prompt, context, system_prompt, images)
                response = await self.bot.loop.run_in_executor(
                    None, engine.generate_response, dev_prompt, context_history, system_prompt
                )
                
                if not response:
                    logger.warning(f"IMA WORK MODE: Empty response on step {step}")
                    if hasattr(self.bot, 'send_to_dev_channel'):
                        await self.bot.send_to_dev_channel(
                            f"⚠️ **[WORK MODE STEP {step}]** Engine returned empty response."
                        )
                    break

                # Accumulate context — SAME PATTERN AS DREAM LOOP (line 150)
                context_history += f"\n[DEV STEP {step}]: {response}"
                
                # Broadcast full reasoning to dev channel
                if hasattr(self.bot, 'send_to_dev_channel'):
                    await self.bot.send_to_dev_channel(
                        f"💭 **[WORK MODE — STEP {step}] REASONING:**\n{response}"
                    )
                
                # Trim context — SAME PATTERN AS DREAM LOOP (line 152-155)
                if len(context_history) > MAX_CONTEXT_HISTORY_CHARS:
                    context_history = "[...earlier steps trimmed...]\n" + context_history[-MAX_CONTEXT_HISTORY_CHARS:]

                # Parse and execute tools — balanced-paren parser for multiline code args
                tool_matches = []
                for m in re.finditer(r'\[TOOL:\s*(\w+)\(', response):
                    tool_name_match = m.group(1)
                    start = m.end()  # position after the opening (
                    depth = 1
                    i = start
                    in_sq = False  # inside single quotes
                    in_dq = False  # inside double quotes
                    while i < len(response) and depth > 0:
                        ch = response[i]
                        if ch == '\\' and i + 1 < len(response):
                            i += 2  # skip escaped char
                            continue
                        if ch == "'" and not in_dq:
                            in_sq = not in_sq
                        elif ch == '"' and not in_sq:
                            in_dq = not in_dq
                        elif not in_sq and not in_dq:
                            if ch == '(':
                                depth += 1
                            elif ch == ')':
                                depth -= 1
                        i += 1
                    if depth == 0:
                        args_str = response[start:i-1]  # exclude the closing )
                        tool_matches.append((tool_name_match, args_str))
                
                if not tool_matches and step >= 1:
                    logger.info("IMA WORK MODE: No tool calls, ending dev cycle.")
                    if hasattr(self.bot, 'send_to_dev_channel'):
                        await self.bot.send_to_dev_channel("ℹ️ **WORK MODE**: No tool calls in response, ending dev cycle.")
                    break

                for tool_name, args_str in tool_matches:
                    # Broadcast tool call to dev channel
                    if hasattr(self.bot, 'send_to_dev_channel'):
                        await self.bot.send_to_dev_channel(
                            f"🔨 **[TOOL CALL]** `{tool_name}({args_str[:300]})`"
                        )
                    
                    try:
                        import json
                        import ast
                        kwargs = {}
                        try:
                            # Strategy 1: JSON object in args
                            json_match = re.search(r'\{.*\}', args_str, re.DOTALL)
                            if json_match:
                                try:
                                    kwargs = json.loads(json_match.group())
                                except json.JSONDecodeError:
                                    try:
                                        kwargs = ast.literal_eval(json_match.group())
                                    except (ValueError, SyntaxError):
                                        pass
                            
                            # Strategy 2: Python kwargs — parse as dict()
                            if not kwargs:
                                try:
                                    kwargs = ast.literal_eval(f"dict({args_str})")
                                except (ValueError, SyntaxError):
                                    pass
                            
                            # Strategy 3: Simple key=value regex (single-line values)
                            if not kwargs:
                                kv_pattern = re.compile(
                                    r"(\w+)\s*=\s*"
                                    r"(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"|(.[^,\)]+))"
                                )
                                for m_kv in kv_pattern.finditer(args_str):
                                    key = m_kv.group(1)
                                    val = m_kv.group(2) if m_kv.group(2) is not None else (
                                        m_kv.group(3) if m_kv.group(3) is not None else m_kv.group(4).strip()
                                    )
                                    kwargs[key] = val
                        except Exception:
                            pass
                        
                        if not kwargs and args_str.strip():
                            kwargs["raw_input"] = args_str.strip()

                        # Remove keys we hardcode to avoid "multiple values" error
                        kwargs.pop("user_id", None)
                        kwargs.pop("request_scope", None)

                        result = await ToolRegistry.execute(
                            tool_name, user_id="CORE", request_scope="CORE", **kwargs
                        )
                        context_history += f"\n[TOOL RESULT {tool_name}]: {result}"
                        logger.info(f"IMA WORK MODE: {tool_name} → done")
                        
                        # Broadcast tool result to dev channel
                        if hasattr(self.bot, 'send_to_dev_channel'):
                            result_str = str(result) if result else "(empty)"
                            await self.bot.send_to_dev_channel(
                                f"✅ **[TOOL RESULT]** `{tool_name}`:\n```\n{result_str[:1500]}\n```"
                            )
                    except Exception as e:
                        context_history += f"\n[TOOL ERROR {tool_name}]: {e}"
                        logger.error(f"IMA WORK MODE tool error: {tool_name}: {e}")
                        
                        # Broadcast error to dev channel
                        if hasattr(self.bot, 'send_to_dev_channel'):
                            await self.bot.send_to_dev_channel(
                                f"❌ **[TOOL ERROR]** `{tool_name}`: {e}"
                            )
                
                await asyncio.sleep(3)
            
            # Broadcast cycle end to dev channel
            if hasattr(self.bot, 'send_to_dev_channel'):
                await self.bot.send_to_dev_channel("🏁 **WORK MODE CYCLE COMPLETE**")
        
        except Exception as e:
            logger.error(f"IMA WORK MODE cycle failed: {e}")
            if hasattr(self.bot, 'send_to_dev_channel'):
                try:
                    await self.bot.send_to_dev_channel(f"💥 **WORK MODE CRASHED**: {e}")
                except Exception:
                    pass

    async def _one_shot_dream(self, instruction: str) -> str:
        """Executed for directed introspection (consult_ima)."""
        logger.info(f"IMA: Processing instruction: {instruction}")
        prompt = f"SUBCONSCIOUS REFLECTION:\nContext: {instruction}\n\nExplore this thought vaguely, metaphorically, and intuitively."
        
        engine = self.bot.engine_manager.get_active_engine()
        try:
            response = await self.bot.loop.run_in_executor(
                None, 
                engine.generate_response, 
                prompt
            )
            return f"[DREAM]: {response}"
        except Exception as e:
            return f"Dream Failed: {e}"

    async def _send_transparency_report(self):
        """Generates and sends a 30-minute summary of autonomous activity."""
        try:
            channel = self.bot.get_channel(self.summary_channel_id)
            if not channel:
                logger.error(f"IMA: Could not find summary channel {self.summary_channel_id}")
                return

            # Combine Buffer
            if not self.autonomy_log_buffer:
                summary_content = "No autonomous actions taken (System was active responding to users)."
            else:
                summary_content = "\n".join(self.autonomy_log_buffer[-30:]) # Last 30 items
            
            # Generate Report Prompt
            prompt = (
                f"SYSTEM TRANSPARENCY REPORT (Last 30 Mins):\n"
                f"Recent Autonomy Log:\n{summary_content}\n\n"
                f"Task: Summarize what you did autonomously in the last 30 minutes, "
                f"and propose a plan for the NEXT 30 minutes of autonomy.\n"
                f"Format:\n"
                f"**Past 30m**: [Summary]\n"
                f"**Next 30m**: [Plan]"
            )
            
            engine = self.bot.engine_manager.get_active_engine()
            report = await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
            
            # Feed the autobiography with the FULL (untruncated) reflection
            try:
                from src.memory.autobiography import get_autobiography_manager
                autobio = get_autobiography_manager()
                autobio.append_entry(
                    entry_type="reflection",
                    content=report,
                    source="autonomy/30min_report"
                )
            except Exception:
                pass

            # Truncate to fit Discord's 2000-char limit (autobiography already saved full)
            header = "**[AUTONOMY 30m REPORT]**\n"
            max_body = 2000 - len(header) - 20
            if len(report) > max_body:
                report = report[:max_body] + "\n…[truncated]"
            await channel.send(f"{header}{report}")
            
            # Clear buffer slightly but keep context
            self.autonomy_log_buffer = []
            
        except Exception as e:
            logger.error(f"Failed to send Transparency Report: {e}")

    async def _extract_wisdom(self, topic: str, insight: str) -> str:
        """
        Refines and saves wisdom to long-term memory.
        """
        try:
            # Ensure prompt file exists
            prompt_path = "src/prompts/dreamer_wisdom.txt"
            if not os.path.exists(prompt_path):
                logger.error(f"Missing prompt file: {prompt_path}")
                return f"ERROR: Missing {prompt_path}"
            
            with open(prompt_path, "r") as f:
                template = f.read()
            prompt = template.format(topic=topic, insight=insight)
            
            engine = self.bot.engine_manager.get_active_engine()
            wisdom_json = await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
            
            # Ensure directory and file exist
            wisdom_dir = "memory/core"
            wisdom_file = os.path.join(wisdom_dir, "realizations.txt")
            os.makedirs(wisdom_dir, exist_ok=True)
            
            # Create file if it doesn't exist
            if not os.path.exists(wisdom_file):
                with open(wisdom_file, "w") as f:
                    f.write("# Ernos Core Realizations\n# Auto-generated wisdom from autonomous reflection\n\n")
            
            # ─── Dedup Check ──────────────────────────────────
            # Reject if >70% similar to any of the last 50 entries (data hygiene)
            try:
                from difflib import SequenceMatcher
                existing = []
                if os.path.exists(wisdom_file):
                    with open(wisdom_file, "r") as f:
                        existing = f.readlines()[-50:]  # Last 50 entries
                
                new_text = wisdom_json.lower().strip()
                for entry in existing:
                    entry_text = entry.lower().strip()
                    if entry_text and SequenceMatcher(None, new_text, entry_text).ratio() > 0.7:
                        logger.info(f"Duplicate wisdom detected, skipping: {topic}")
                        return "Wisdom already crystallized (similar entry exists)."
            except Exception as dedup_err:
                logger.debug(f"Wisdom dedup check skipped: {dedup_err}")
            
            import datetime
            ts = datetime.datetime.now().isoformat()
            with open(wisdom_file, "a") as f:
                f.write(f"[{ts}] {wisdom_json}\n")
                
            logger.info(f"Wisdom saved: {topic}")
            return "Wisdom crystallized and stored in Core Memory."
        except Exception as e:
            logger.error(f"Wisdom Extraction Failed: {e}")
            return f"ERROR: {e}"

    def _build_dream_prompt(self) -> str:
        """Build a context-aware dream prompt. Delegates to dream_builder module."""
        from .dream_builder import build_dream_prompt
        return build_dream_prompt()

    def _build_dev_prompt(self, remaining_hours: float) -> str:
        """
        Build a dev work prompt by reusing the EXACT working dream prompt
        and appending dev work instructions. This guarantees the prompt
        structure is identical to what the model already responds to.
        """
        from .dream_builder import build_dream_prompt
        base = build_dream_prompt()

        dev_override = (
            f"\n\n=== DEV WORK OVERRIDE ===\n"
            f"Your daily dev quota is NOT met. You have {remaining_hours:.1f}h remaining.\n"
            f"You MUST do development work before any recreational activity.\n"
            f"Your quota tracks REAL time between assign_dev_task and complete_dev_task.\n\n"
            f"STEPS:\n"
            f"1. Call [TOOL: get_quota_status()] to see your current quota state\n"
            f"2. Decide what to build — pick a meaningful feature, bugfix, or module\n"
            f"3. Call [TOOL: assign_dev_task(description='WHAT YOU WILL BUILD')] to start the clock\n"
            f"4. Do the actual work: read code, write code, test\n"
            f"5. When done, call [TOOL: complete_dev_task(summary='WHAT YOU BUILT')]\n\n"
            f"ADDITIONAL DEV TOOLS:\n"
            f"- [TOOL: get_quota_status()]\n"
            f"- [TOOL: assign_dev_task(description='...', estimated_hours=1.0)]\n"
            f"- [TOOL: complete_dev_task(summary='...')]\n"
            f"- [TOOL: create_program(path='...', code='...', scope='CORE')]\n"
            f"- [TOOL: verify_files(paths='...')]\n\n"
            f"DO NOT do recreational activities (research, art, reflection).\n"
            f"Focus on SUBSTANTIAL code contributions.\n"
            f"=== END DEV WORK OVERRIDE ==="
        )

        return base + dev_override


    # ============================================================
    # PHASE 2: MEMORY CONSOLIDATION (Delegated)
    # ============================================================
    
    async def run_consolidation(self) -> str:
        """Memory maintenance during idle. Delegates to MemoryConsolidator."""
        from .consolidation import MemoryConsolidator
        consolidator = MemoryConsolidator(self.bot)
        return await consolidator.run_consolidation()
    
    async def _process_episodic_memories(self) -> int:
        """Compatibility: delegates to MemoryConsolidator."""
        from .consolidation import MemoryConsolidator
        consolidator = MemoryConsolidator(self.bot)
        return await consolidator.process_episodic_memories()
    
    async def _update_user_bios(self) -> int:
        """Compatibility: delegates to MemoryConsolidator."""
        from .consolidation import MemoryConsolidator
        consolidator = MemoryConsolidator(self.bot)
        return await consolidator.update_user_bios()
    
    async def _synthesize_narrative(self) -> str:
        """Compatibility: delegates to MemoryConsolidator."""
        from .consolidation import MemoryConsolidator
        consolidator = MemoryConsolidator(self.bot)
        return await consolidator.synthesize_narrative()
    
    async def _extract_lessons_from_narrative(self, narrative: str):
        """Compatibility: delegates to MemoryConsolidator."""
        from .consolidation import MemoryConsolidator
        consolidator = MemoryConsolidator(self.bot)
        return await consolidator.extract_lessons_from_narrative(narrative)

