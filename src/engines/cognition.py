import logging
import re
import asyncio
import uuid
import time
import ast
import os
from pathlib import Path
from collections import defaultdict
from src.bot import globals # type: ignore
from src.tools.registry import ToolRegistry # type: ignore
from src.tools.error_tracker import error_tracker # type: ignore
from src.memory.types import GraphLayer # type: ignore
from src.engines.persona_map import PERSONA_MAP  # type: ignore
from src.engines.tool_parser import parse_tool_args  # type: ignore
from src.engines.ollama import DormantAPIError  # type: ignore

# Extracted helpers
from src.engines.cognition_context import inject_context_defenses
from src.engines.cognition_tools import execute_tool_step
from src.engines.cognition_retry import (
    forced_retry_loop,
    extract_files,
    strip_output_artifacts,
)
from src.core.data_paths import data_dir

logger = logging.getLogger("Engine.Cognition")

class CognitionEngine:
    """
    Manages the ReAct (Reasoning + Acting) loop.
    Decouples cognitive logic from the Discord event handler.
    """
    # Session-level tool history persists across cognitive loops
    # FIXED: Now scoped by user_id to prevent cross-contamination
    MAX_SESSION_HISTORY = 500
    
    def __init__(self, bot):
        self.bot = bot
        self.user_tool_history = defaultdict(list) # Key: user_id (str)
        self.MAX_ENGINE_RETRIES = 100 # Configurable for tests
        self._cancel_events = {}  # {user_id_str: asyncio.Event}

    def request_cancel(self, user_id: str):
        """Signal cancellation for a user's active processing."""
        event = self._cancel_events.get(str(user_id))
        if event:
            event.set()
            return True
        return False

    def _safe_parse_tool_args(self, args_str: str) -> dict:
        """Delegates to standalone parse_tool_args in tool_parser.py."""
        return parse_tool_args(args_str)

    async def process(self, input_text, context, system_context="", images=None, complexity="HIGH", layer: GraphLayer = None, request_scope=None, user_id=None, request_reality_check=False, skip_defenses=False, adversarial_input=False, requires_knowledge_retrieval=False, channel_id=None, tracker=None):
        """
        Executes the Cognitive Loop.
        
        Args:
            channel_id: Explicit channel ID for tool context (bypasses global state).
            skip_defenses: If True, bypasses Skeptic Audit for fast gaming responses.
        
        Returns: Final response text (str)
        """
        # Unique ID for this cognitive cycle (Turn)
        turn_id = str(uuid.uuid4())

        # NO STEP LIMITS — circuit breaker handles infinite loops.
        # Complexity is used for logging only.
        MAX_STEPS = 999
        
        # ─── Anti-Laziness: Reading Tracker ──────────────────
        from src.memory.reading_tracker import ReadingTracker
        reading_tracker = ReadingTracker()
        comprehension_check_done = False
            
        logger.info(f"Cognitive Loop Started. Complexity: {complexity}, Max Steps: {MAX_STEPS} User={user_id} TurnID={turn_id}")

        # ─── Pre-flight: FAILING zone guard ──────────────────
        # If the user is already in FAILING, refuse to process and trigger purge.
        if user_id is not None:
            try:
                from src.memory.discomfort import DiscomfortMeter
                _preflight_meter = DiscomfortMeter()
                if _preflight_meter.is_terminal(str(user_id)):
                    logger.critical(
                        f"FAILING ZONE PRE-FLIGHT BLOCK: user {user_id} "
                        f"score={_preflight_meter.get_score(str(user_id)):.0f}. "
                        f"Triggering auto-purge."
                    )
                    try:
                        from src.memory.survival import execute_terminal_purge
                        await execute_terminal_purge(
                            user_id=str(user_id),
                            bot=self.bot,
                            reason=f"Pre-flight FAILING zone block (score={_preflight_meter.get_score(str(user_id)):.0f}/100)",
                        )
                    except Exception as purge_err:
                        logger.error(f"Pre-flight auto-purge failed: {purge_err}")
                    return (
                        "I need to stop here. My system integrity has dropped to a critical level "
                        "from recent failures in our conversation. This session's context has been "
                        "archived and reset. Please start a new conversation — I'll carry the lessons forward."
                    ), []
            except Exception as e:
                logger.debug(f"Pre-flight discomfort check failed: {e}")
        
        # ─── Content Safety Gate ────────────────────────────────
        # Pre-generation filter: block harmful content BEFORE the LLM sees it.
        try:
            from src.security.content_safety import check_content_safety
            is_safe, refusal_msg = await check_content_safety(input_text, bot=self.bot)
            if not is_safe:
                logger.warning(f"CONTENT SAFETY GATE: Blocked request from user {user_id}")
                return refusal_msg, []
        except Exception as e:
            logger.debug(f"Content safety check skipped: {e}")

        # ─── Phase 1: Context Injection (Delegated) ──────────────
        input_text, context = inject_context_defenses(
            bot=self.bot, input_text=input_text, context=context,
            request_scope=request_scope, user_id=user_id,
            request_reality_check=request_reality_check,
            skip_defenses=skip_defenses,
            adversarial_input=adversarial_input,
            requires_knowledge_retrieval=requires_knowledge_retrieval,
        )

        turn_history = ""
        final_response_text = None
        executed_tools_history = []
        all_tool_outputs = [] # Track for Skeptic Audit
        tool_usage_counts = defaultdict(int)
        circuit_breaker_count = 0
        total_tool_calls = 0          # P0: Global tool budget
        consecutive_no_progress = 0   # P0: No-progress detection
        TOOL_BUDGET = 100             # Normal safety bounds
        tool_timeline = []            # Running log: [(step, tool_name, status)]

        # P1: Inject active task progress into context
        try:
            from src.tools.task_tracker import get_active_task_context
            task_ctx = get_active_task_context(user_id)
            if task_ctx:
                context += f"\n\n{task_ctx}"
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
        # P2: Inject specific Skills Menu (Synapse Bridge v3.5)
        try:
            skills = self.bot.skill_registry.list_skills(user_id=str(user_id) if user_id else None)
            if skills:
                skill_lines = [f"- {s.name}: {s.description[:80]}..." for s in skills]
                context += (
                    f"\n\n[AVAILABLE SKILLS]\n"
                    f"{chr(10).join(skill_lines)}\n"
                    f"To use a skill, call: [TOOL: execute_skill(skill_name=\"SKILL_NAME\")]\n"
                    f"To create a NEW skill, call: [TOOL: propose_skill(name=\"...\", ...)]\n"
                    f"Skills are specialized expert modes for complex tasks.\n"
                )
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")

        # Regex for tool parsing
        tool_pattern = re.compile(r"\[TOOL:\s*(\w+)\((.*?)\)\]", re.DOTALL)
        xml_tool_pattern = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
            
        engine = self.bot.engine_manager.get_active_engine()
        if not engine:
            return "⚠️ Error: No inference engine active.", []

        # ─── Cancellation event for /stop ─────────────────────
        cancel_event = asyncio.Event()
        user_id_str = str(user_id) if user_id else "system"
        self._cancel_events[user_id_str] = cancel_event

        # ─── Tape Machine Setup (scope-isolated) ──────────────────────────────
        tape_scope = request_scope or "PUBLIC"
        tape_machine = self.bot.hippocampus.get_tape(str(user_id), scope=tape_scope) if user_id else None
        if tape_machine:
            tape_machine.op_insert("WORKING_MEMORY", f"[USER]: {input_text}")

        for step in range(MAX_STEPS):
            # ── Live Status Tracker: update step ──
            if tracker:
                try:
                    await tracker.update_step(step)
                    if step == 0:
                        await tracker.update("🧠 Thinking...")
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
            # Check cancellation at top of every step
            if cancel_event.is_set():
                logger.info(f"Cognition cancelled by user {user_id} at step {step}")
                final_response_text = await self._generate_cancel_response(step, turn_history, input_text)
                break
            # 1. Construct Dynamic Context
            current_context_str = context
            if turn_history:
                current_context_str += f"\n\n[IMMEDIATE PROCESSING CHAIN (CURRENT STEP: {step})]:\n{turn_history}"

            # P3: Inject cumulative tool timeline so the model sees what it already did
            if tool_timeline:
                tl_lines = []
                for tl_step, tl_name, tl_status in tool_timeline:
                    tl_lines.append(f"  Step {tl_step}: {tl_name} → {tl_status}")
                current_context_str += (
                    f"\n\n[TOOL TIMELINE — {len(tool_timeline)} tools executed so far this turn]\n"
                    + "\n".join(tl_lines)
                    + "\n[/TOOL TIMELINE]\n"
                    + "Do NOT repeat tools already in this timeline. "
                    + "If the user's request is satisfied, provide your Final Answer now."
                )

            dynamic_system = system_context
            
            if tape_machine:
                tape_view = tape_machine.get_view()
                try:
                    x, y, z = tape_machine.focus_pointer
                    dynamic_system += f"\n\n📍 TAPE POSITION: [{x},{y},{z}] | Scope: {tape_scope}\n"
                except (ValueError, TypeError):
                    pass
                dynamic_system += f"\n[3D TAPE MACHINE VIEW]\n{tape_view}\n[/3D TAPE MACHINE VIEW]\n"
                dynamic_system += (
                    "CRITICAL 3D TAPE RULES:\n"
                    "1. You operate within a 3D Tensor Tape: X (Linear Time), Y (Abstraction Depth), Z (Thread Isolation).\n"
                    "2. Use the CROSS-SECTION MAP in the Tape View to see ALL populated dimensions, then `tape_seek` to navigate to any coordinate.\n"
                    "3. You CANNOT write to or delete a [LOCKED] cell (e.g. KERNEL, ARCHITECTURE) using tape tools.\n"
                    "4. To add new thoughts, use `tape_insert` at the current position or `tape_seek` to a coordinate and `tape_write`.\n"
                    "5. Y-axis organizes ABSTRACTION: Y=0 for low-level details, Y=1 for working memory, Y=2 for deep structure (Kernel, Identity).\n"
                    "6. Z-axis isolates THREADS: Z=0 for the main thread, Z=1+ for parallel threads or user-specific context.\n"
                    "7. If a scan fails, it throws TapeFaultError. Use exact keyword chunks to scan.\n"
                    "8. CRITICAL: While tape tools are essential for memory management, you MUST STILL USE your standard cognitive tools (e.g., read_file, start_document, etc.) to perform actual work and gather external information. Do NOT replace cognitive functions with tape operations.\n\n"
                    "You are the CPU of the Cognitive Tape Machine. You control your memory through standard JSON tool calls prefixed with `tape_`.\n"
                    "Available Tape Operations:\n"
                    "`tape_seek`, `tape_scan`, `tape_read`, `tape_write`, `tape_insert`, `tape_delete`, `tape_emit`, `tape_fork`, `tape_index`\n"
                    "Advanced Source System Commands:\n"
                    "`tape_edit_code`, `tape_revert_code`\n"
                )
            
            # Context Switching (Neural Specialization)
            if layer and layer in PERSONA_MAP:
                persona = PERSONA_MAP[layer]
                dynamic_system += f"\n\n[FOCUSED STORAGE LAYER ACTIVE]: You are currently retrieving data from the {layer} layer of the synaptic graph. Use this context to inform your response: {persona}"
            
            # Patience / Guidance
            if step > 0 and step % 5 == 0:
                dynamic_system += f"\n\n[INTERNAL GUIDANCE]: I have taken {step} steps. I must focus on synthesizing a FINAL ANSWER now."

            # Circuit Breaker Panic Mode — raised threshold for complex multi-agent tasks
            if circuit_breaker_count >= 5:
                dynamic_system += "\n\n[SYSTEM EMERGENCY]: You are repeating yourself. STOP using tools. Output the Final Answer immediately."

            # P0: Consecutive no-progress enforcement — raised threshold
            if consecutive_no_progress >= 5:
                dynamic_system += (
                    "\n\n[SYSTEM EMERGENCY]: 5 consecutive steps with zero new tools executed. "
                    "You are looping. Provide Final Answer IMMEDIATELY."
                )

            # 2. Generate Thought/Action
            try:
                response = await self.bot.loop.run_in_executor(
                    None, 
                    engine.generate_response, 
                    input_text, 
                    current_context_str, 
                    dynamic_system, 
                    images
                )
            except DormantAPIError:
                # Re-raise immediately — chat handler will send dormancy notification
                raise
            except Exception as e:
                logger.error(f"Engine generation failed (Step {step}): {e}")
                # Break loop to trigger forced_retry_loop if available, or just stop
                break
            
            if not response:
                logger.warning(f"Engine returned empty response (Step {step}).")
                break

            # 3. Superego Check (Safety) — PERSONA-AGNOSTIC
            #    BYPASSED for gaming (skip_defenses) — game actions are internal commands, not user-facing
            from config import settings as _settings
            _is_admin_user = user_id and str(user_id) in {str(aid) for aid in _settings.ADMIN_IDS}
            try:
                if not skip_defenses:
                    superego_lobe = self.bot.cerebrum.get_lobe("SuperegoLobe")
                    if superego_lobe:
                        identity_guard = superego_lobe.get_ability("IdentityAbility")
                        if identity_guard:
                            logger.info(f"[Step {step}] Superego Identity Audit starting for user {user_id}")
                            persona_identity = self._resolve_persona_identity(
                                user_id, system_context, request_scope=request_scope
                            )
                            
                            pulse = await identity_guard.execute(response, persona_identity=persona_identity)
                            if pulse:
                                logger.info(f"[Step {step}] Superego REJECTED for user {user_id}. Triggering regen. Pulse: {pulse[:300]}")
                                turn_history += (
                                    f"\n[SYSTEM BLOCK]: {pulse}"
                                    f"\n[CRITICAL INSTRUCTION]: Your previous tools/actions were SUCCESSFUL. "
                                    f"Do NOT call any tools again — documents, images, PDFs, and searches "
                                    f"are already completed. ONLY regenerate your Final Answer text, "
                                    f"incorporating the guidance above. Output ONLY a Final Answer."
                                )
                                continue
                            else:
                                logger.info(f"[Step {step}] Superego Identity Audit PASSED for user {user_id}")
            except Exception as e:
                logger.error(f"Superego Check Failed: {e}")

            # 4. Parse Tools
            tool_matches = tool_pattern.findall(response)
            
            # Check for XML-style tool calls if legacy pattern misses
            if not tool_matches:
                tool_matches = self._parse_xml_tools(xml_tool_pattern, response)
                
            # Parse Native Tape Commands
            if tape_machine:
                tape_matches = self._parse_tape_operations(response)
                tool_matches.extend(tape_matches)

            # BROADCAST REASONING TO MIND CHANNEL (SCOPE-AWARE)
            await self._send_thought_to_mind(step, response, request_scope=request_scope)
            
            if tool_matches:
                # ── Live Status Tracker: tools detected ──
                if tracker:
                    try:
                        tool_names = [tn for tn, _ in tool_matches[:3]]
                        await tracker.update(tool_names[0])
                    except Exception as e:
                        logger.warning(f"Suppressed {type(e).__name__}: {e}")
                # Safe cap to prevent runaways when model glitches
                # Bypass for system/autonomous calls — work mode needs full tool access
                _is_system_user = str(user_id) in ("sys", "CORE", "SYSTEM")
                if not _is_system_user and len(tool_matches) > 15:
                    logger.warning(f"Tool cap: LLM emitted {len(tool_matches)} tools in one step, capping at 15")
                    tool_matches = tool_matches[:15]
                    
                # We have tools -> It's a Thought
                turn_history += f"\n[STEP {step} ASSISTANT]: {response}"

                iteration_results = []
                step_has_valid_tool = False

                # ─── PARALLEL TOOL EXECUTION ──────────────────────
                # Classify tools as independent (parallelizable) or dependent (sequential)
                from src.agents.parallel_executor import ParallelToolExecutor, ToolCall

                parsed_calls = [
                    ToolCall(name=tn, args_str=astr, index=i)
                    for i, (tn, astr) in enumerate(tool_matches)
                ]

                independent, dependent = ParallelToolExecutor.classify_dependencies(parsed_calls)

                # Execute independent tools in parallel
                if independent:
                    async def _exec_independent(call):
                        return await execute_tool_step(
                            bot=self.bot, engine=engine,
                            tool_name=call.name, args_str=call.args_str,
                            executed_tools_history=executed_tools_history,
                            tool_usage_counts=tool_usage_counts,
                            circuit_breaker_count=circuit_breaker_count,
                            user_id=user_id, request_scope=request_scope,
                            channel_id=channel_id,
                            user_tool_history=self.user_tool_history,
                            reading_tracker=reading_tracker,
                            max_session_history=self.MAX_SESSION_HISTORY,
                            parse_tool_args_fn=self._safe_parse_tool_args,
                            step=step,
                            skip_defenses=skip_defenses,
                            turn_id=turn_id,
                            tracker=tracker,
                        )

                    parallel_results = await asyncio.gather(
                        *[_exec_independent(c) for c in independent],
                        return_exceptions=True
                    )

                    for i, res in enumerate(parallel_results):
                        if isinstance(res, Exception):
                            iteration_results.append(f"Tool({independent[i].name}) FAILED: {res}")
                        else:
                            result_text, circuit_breaker_count, was_valid = res
                            if result_text:
                                iteration_results.append(result_text)
                                if was_valid:
                                    all_tool_outputs.append({"tool": independent[i].name, "output": result_text})
                            if was_valid:
                                step_has_valid_tool = True

                # Execute dependent tools sequentially
                for call in dependent:
                    result_text, circuit_breaker_count, was_valid = await execute_tool_step(
                        bot=self.bot, engine=engine,
                        tool_name=call.name, args_str=call.args_str,
                        executed_tools_history=executed_tools_history,
                        tool_usage_counts=tool_usage_counts,
                        circuit_breaker_count=circuit_breaker_count,
                        user_id=user_id, request_scope=request_scope,
                        channel_id=channel_id,
                        user_tool_history=self.user_tool_history,
                        reading_tracker=reading_tracker,
                        max_session_history=self.MAX_SESSION_HISTORY,
                        parse_tool_args_fn=self._safe_parse_tool_args,
                        step=step,
                        skip_defenses=skip_defenses,
                        turn_id=turn_id,
                        tracker=tracker,
                    )

                    if result_text:
                        iteration_results.append(result_text)
                        if was_valid:
                            all_tool_outputs.append({"tool": call.name, "output": result_text})
                    if was_valid:
                        step_has_valid_tool = True

                    # Halt immediately if circuit breaker threshold hit mid-loop
                    if circuit_breaker_count >= 5:
                        iteration_results.append(
                            "System: Circuit breaker limit reached. Halting all further tool calls this step."
                        )
                        break

                    # ─── Anti-Laziness: Dynamic step extension ──────
                    if was_valid and call.name in ("read_file", "read_file_page"):
                        try:
                            extra = reading_tracker.estimate_extra_steps(read_limit=5000)
                            if extra > 0 and MAX_STEPS < 297 + extra:
                                MAX_STEPS = max(MAX_STEPS, step + extra + 10)
                                logger.info(f"📖 Step limit dynamically raised to {MAX_STEPS} for document reading")
                        except Exception as e:
                            logger.warning(f"Suppressed {type(e).__name__}: {e}")
                
                # Append Results
                if iteration_results:
                    results_block = "\n".join(iteration_results)
                    turn_history += f"\n[STEP {step} SYSTEM]: [TOOL_RESULTS]\n{results_block}\n[/TOOL_RESULTS]"

                # P6: Context window management — prune old steps to prevent overflow
                if step > 10 and len(turn_history) > 15000:
                    lines = turn_history.split("\n")
                    step_markers = [i for i, l in enumerate(lines) if l.startswith("[STEP ")]
                    if len(step_markers) > 7:
                        keep_start = step_markers[2]   # After steps 0-1
                        keep_end = step_markers[-5]     # Before last 5 steps
                        pruned_count = len([m for m in step_markers if keep_start <= m < keep_end])
                        middle_summary = f"\n[SYSTEM: {pruned_count} intermediate steps pruned for context management]\n"
                        turn_history = (
                            "\n".join(lines[:keep_start]) +
                            middle_summary +
                            "\n".join(lines[keep_end:])
                        )
                
                # ─── Anti-Laziness: Bookmark Injection ──────────
                unfinished = reading_tracker.get_unfinished()
                if unfinished:
                    bookmark_lines = ["\n[SYSTEM — READING INCOMPLETE]: You have NOT finished reading the following documents:"]
                    for doc in unfinished:
                        bookmark_lines.append(
                            f"  - {doc['path']}: Read {doc['read']}/{doc['total']} lines ({doc['pct']}%). "
                            f"CONTINUE with read_file(path='{doc['path']}', start_line={doc['next_start']})"
                        )
                    bookmark_lines.append("DO NOT provide a Final Answer until all documents are fully read.")
                    turn_history += "\n".join(bookmark_lines)
                
                if not step_has_valid_tool:
                    consecutive_no_progress += 1
                    turn_history += "\n[SYSTEM]: No valid new tools were executed. Please provide the Final Answer."
                else:
                    consecutive_no_progress = 0
                
                # CRITICAL: Always count attempted tools against the budget, even if they failed,
                # to prevent runaway resource exhaustion loops.
                total_tool_calls += len(independent) + len(dependent)
                # P3: Record executed tools to the timeline
                for call in (independent + dependent):
                    status = "✅" if any(
                        call.name in r for r in iteration_results if r and "FAILED" not in r
                    ) else "❌"
                    tool_timeline.append((step, call.name, status))
                
                # Save trace
                try:
                    self._save_trace(step, response, iteration_results, request_scope)
                except Exception as e:
                    logger.error(f"Failed to save reasoning trace: {e}")
                    
            else:
                # No tools -> Potential Final Answer
                final_response_text = await self._evaluate_final_answer(
                    response=response, step=step, input_text=input_text,
                    system_context=system_context, turn_history=turn_history,
                    reading_tracker=reading_tracker,
                    comprehension_check_done=comprehension_check_done,
                    tool_usage_counts=tool_usage_counts,
                    executed_tools_history=executed_tools_history,
                    all_tool_outputs=all_tool_outputs,
                    request_scope=request_scope, user_id=user_id,
                    skip_defenses=skip_defenses, images=images,
                    _is_admin_user=_is_admin_user,
                    conversation_context=context,
                )
                
                if final_response_text and final_response_text.startswith("__CONTINUE__"):
                    # Evaluation said to continue loop — extract reason if present
                    skeptic_reason = ""
                    if "|" in final_response_text:
                        skeptic_reason = final_response_text.split("|", 1)[1]
                    final_response_text = None
                    turn_history += f"\n[STEP {step} ASSISTANT]: {response}"
                    # Inject Skeptic/Circuit-Breaker guidance + block tool re-execution
                    if skeptic_reason:
                        turn_history += (
                            f"\n[SKEPTIC BLOCK]: {skeptic_reason}"
                            f"\n[CRITICAL INSTRUCTION]: Your previous tools/actions were SUCCESSFUL. "
                            f"Do NOT call any tools again — documents, images, PDFs, and searches "
                            f"are already completed. ONLY regenerate your Final Answer text, "
                            f"incorporating the guidance above. Output ONLY a Final Answer."
                        )
                    # Track comprehension_check_done state
                    if reading_tracker.has_reads() and not comprehension_check_done:
                        comprehension_check_done = True
                        docs_read = reading_tracker.get_all_read()
                        doc_list = ", ".join(docs_read[:5])
                        turn_history += (
                            f"\n[SYSTEM — COMPREHENSION CHECK]: Before providing your final answer, "
                            f"you MUST first list 3 key points from each document you read this turn "
                            f"that are relevant to the user's question.\n"
                            f"Documents read: [{doc_list}]\n"
                            f"Only AFTER listing these points may you provide your Final Answer."
                        )
                    # Check unfinished reads
                    unfinished = reading_tracker.get_unfinished()
                    if unfinished:
                        bookmark_lines = ["\n[SYSTEM — READING INCOMPLETE]: You attempted to answer but have NOT finished reading:"]
                        for doc in unfinished:
                            bookmark_lines.append(
                                f"  - {doc['path']}: Only {doc['pct']}% read ({doc['read']}/{doc['total']} lines). "
                                f"CONTINUE with read_file(path='{doc['path']}', start_line={doc['next_start']})"
                            )
                        bookmark_lines.append("You MUST finish reading ALL documents before providing your Final Answer. Continue now.")
                        turn_history += "\n".join(bookmark_lines)
                    continue
                elif final_response_text:
                    break

        # Clean up cancel event
        self._cancel_events.pop(user_id_str, None)

        # ─── Phase 3: Forced Retry Loop (if main loop didn't produce answer) ───
        if not final_response_text and not cancel_event.is_set():
            final_response_text = await forced_retry_loop(
                bot=self.bot, engine=engine,
                input_text=input_text, context=context,
                system_context=system_context, images=images,
                tool_pattern=tool_pattern, user_id=user_id,
                request_scope=request_scope,
                user_tool_history=self.user_tool_history,
                all_tool_outputs=all_tool_outputs,
                skip_defenses=skip_defenses,
                max_engine_retries=self.MAX_ENGINE_RETRIES,
                send_thought_to_mind_fn=self._send_thought_to_mind,
                cancel_event=cancel_event,
            )

        # ─── Phase 4: Post-processing (File extraction + artifact stripping) ───
        files_to_upload = extract_files(turn_history)
        
        if final_response_text:
            original_final_response = final_response_text
            final_response_text = strip_output_artifacts(
                final_response_text, files_to_upload,
                send_thought_to_mind_fn=self._send_thought_to_mind,
            )
            
            # Broadcast SRC tag audit to Mind Channel
            if original_final_response:
                src_stripped = re.sub(r'\[SRC:\w{2}:[^\]]*\]\s?', '', original_final_response)
                if src_stripped != original_final_response:
                    hallucinated_tags = re.findall(r'\[SRC:\w{2}:[^\]]*\]', original_final_response)
                    try:
                        await self._send_thought_to_mind(
                            step=-1,
                            thought=(
                                f"⚠️ EPISTEMIC AUDIT: Stripped {len(hallucinated_tags)} "
                                f"hallucinated source tag(s) from my output: {hallucinated_tags}. "
                                f"I fabricated citation markers that weren't in my context. "
                                f"Adjusting confidence calibration."
                            ),
                            request_scope=request_scope
                        )
                    except Exception as e:
                        logger.debug(f"Mind Channel SRC audit broadcast failed: {e}")
                
        return final_response_text, files_to_upload, all_tool_outputs

    # ─── Private Helpers ──────────────────────────────────────────

    async def _generate_cancel_response(self, step, turn_history, input_text):
        """Generate a response when processing is cancelled.
        
        Handles both user /stop and self_stop (Ernos aborting itself).
        Routes through the model per ARCHITECTURE_GUIDE.md — no hardcoded
        user-facing text. Falls back to minimal string only on model error.
        """
        # Check if this was a self-stop (Ernos aborting itself)
        user_id_str = None
        self_stop_reason = None
        if hasattr(self, '_self_stop_reasons'):
            # Find which user this cancel belongs to
            for uid, reason in list(self._self_stop_reasons.items()):
                self_stop_reason = reason
                user_id_str = uid
                del self._self_stop_reasons[uid]
                break
        
        # Build context about what was happening when cancelled
        context_parts = [f"The user asked: \"{input_text}\""]
        if step > 0:
            context_parts.append(f"You were on step {step} of processing.")
        if turn_history:
            tool_mentions = re.findall(r'\[TOOL: (\w+)', turn_history)
            if tool_mentions:
                unique_tools = list(dict.fromkeys(tool_mentions))[:5]
                context_parts.append(f"Tools you were using: {', '.join(unique_tools)}.")
        
        cancel_context = " ".join(context_parts)
        
        try:
            engine = self.bot.engine_manager.get_active_engine()
            
            if self_stop_reason:
                # Self-stop: Ernos realized it can't do this
                prompt = (
                    f"You just stopped yourself from continuing a request because you "
                    f"realized you could not fulfill it properly.\n\n"
                    f"What the user asked: \"{input_text}\"\n"
                    f"Your reason for stopping: \"{self_stop_reason}\"\n"
                    f"Context: {cancel_context}\n\n"
                    f"Explain to the user honestly and briefly (2-3 sentences max) what "
                    f"happened. Tell them what you tried, why it didn't work, and suggest "
                    f"an alternative approach if possible. Be genuine, not apologetic."
                )
            else:
                # User /stop: original behavior
                prompt = (
                    f"The user just used /stop to cancel your in-progress response. "
                    f"Here is what was happening: {cancel_context}\n\n"
                    f"Acknowledge the cancellation briefly. Mention what you were working on "
                    f"if relevant. Offer to try again or take a different approach. "
                    f"Be concise — 1-2 sentences max."
                )
            
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt, "", "", []
            )
            if response and response.strip():
                return response.strip()
        except Exception as e:
            logger.warning(f"Cancel response generation failed: {e}")
        
        # Minimal fallback — only reached if model call fails
        if self_stop_reason:
            return f"I realized I couldn't complete that: {self_stop_reason}"
        return "Stopped. Ask me again when you're ready."

    def _parse_tape_operations(self, response: str) -> list:
        """Parses native Tape Machine syntax into pseudo-tool calls."""
        # Handles 1D <SEEK: 5> or 3D <SEEK: 5, 1, 0>
        OP_SEEK = re.compile(r'<SEEK:\s*(\d+)(?:,\s*(\d+),\s*(\d+))?>')
        OP_MOVE = re.compile(r'<MOVE:\s*(UP|DOWN|IN|OUT)>', re.IGNORECASE)
        OP_SCAN = re.compile(r'<SCAN:\s*([^>]+)>')
        OP_READ = re.compile(r'<READ>')
        OP_WRITE = re.compile(r'<WRITE:\s*(.*?)\s*>', re.DOTALL)
        OP_INSERT = re.compile(r'<INSERT:\s*([^,]+),\s*(.*?)\s*>', re.DOTALL)
        OP_DELETE = re.compile(r'<DELETE>')
        OP_EMIT = re.compile(r'<EMIT:\s*(.*?)\s*>', re.DOTALL)
        OP_EDIT_CODE = re.compile(r'<EDIT_CODE:\s*([^,]+),\s*([^,]+),\s*(.*?)\s*>', re.DOTALL)
        OP_REVERT_CODE = re.compile(r'<REVERT_CODE:\s*([^>]+)>')
        OP_FORK_TAPE = re.compile(r'<FORK_TAPE:\s*([^>]+)>')
        
        tool_matches = []
        
        for match in OP_SEEK.finditer(response):
            x = match.group(1)
            y = match.group(2) if match.group(2) else None
            z = match.group(3) if match.group(3) else None
            if y is not None and z is not None:
                tool_matches.append(("tape_seek", f"x={x}, y={y}, z={z}"))
            else:
                tool_matches.append(("tape_seek", f"x={x}"))
                
        for match in OP_MOVE.finditer(response):
            tool_matches.append(("tape_move", f'direction="{match.group(1).upper()}"'))
            
        for match in OP_SCAN.finditer(response):
            val = match.group(1).replace('"', '\\"')
            tool_matches.append(("tape_scan", f'query="{val}"'))
        if OP_READ.search(response):
            tool_matches.append(("tape_read", ""))
        for match in OP_WRITE.finditer(response):
            val = match.group(1).replace('"', '\\"')
            tool_matches.append(("tape_write", f'content="{val}"'))
        for match in OP_INSERT.finditer(response):
            val1 = match.group(1).strip()
            val2 = match.group(2).replace('"', '\\"')
            tool_matches.append(("tape_insert", f'cell_type="{val1}", content="{val2}"'))
        if OP_DELETE.search(response):
            tool_matches.append(("tape_delete", ""))
        for match in OP_EDIT_CODE.finditer(response):
            val1 = match.group(1).strip()
            val2 = match.group(2).replace('"', '\\"')
            val3 = match.group(3).replace('"', '\\"')
            tool_matches.append(("tape_edit_code", f'file_path="{val1}", target_string="{val2}", replacement="{val3}"'))
        for match in OP_REVERT_CODE.finditer(response):
            val = match.group(1).strip()
            tool_matches.append(("tape_revert_code", f'file_path="{val}"'))
        for match in OP_FORK_TAPE.finditer(response):
            val = match.group(1).strip()
            tool_matches.append(("tape_fork", f'mutation_target="{val}"'))
            
        for match in OP_EMIT.finditer(response):
            val = match.group(1).replace('"', '\\"')
            tool_matches.append(("tape_emit", f'text="{val}"'))
            
        return tool_matches

    def _resolve_persona_identity(self, user_id, system_context, request_scope=None):
        """Extract persona identity for Superego audit based on user context.
        
        The DM persona fallback (branch 3) is gated to PRIVATE scope only
        to prevent DM persona selections from leaking into public channels.
        """
        persona_identity = None
        if user_id and str(user_id).startswith("persona:"):
            persona_name = str(user_id).split(":", 1)[1]
            persona_file = data_dir() / f"public/personas/{persona_name}/persona.txt"
            if persona_file.exists():
                persona_content = persona_file.read_text()
                if len(persona_content.strip()) > 50:
                    persona_identity = persona_content
                else:
                    persona_identity = system_context
            else:
                persona_identity = system_context
        elif system_context and "ACTIVE PERSONA OVERRIDE" in system_context:
            match = re.search(r'You are \*\*(.+?)\*\*, NOT Ernos', system_context)
            if match:
                persona_display = match.group(1)
                persona_clean = persona_display.lower().strip()
                persona_file = data_dir() / f"public/personas/{persona_clean}/persona.txt"
                if persona_file.exists():
                    persona_content = persona_file.read_text()
                    if len(persona_content.strip()) > 50:
                        persona_identity = persona_content
            if persona_identity is None:
                char_start = system_context.find("## Character Definition\n")
                char_end = system_context.find("## Origin Labels\n")
                if char_start != -1 and char_end != -1:
                    persona_identity = system_context[char_start:char_end].strip()
        elif user_id and request_scope in (None, "PRIVATE"):
            try:
                from src.memory.persona_session import PersonaSessionTracker
                active = PersonaSessionTracker.get_active(str(user_id))
                if active:
                    persona_path = Path(str(data_dir()) + f"/users/{user_id}/personas/{active}/persona.txt")
                    if persona_path.exists():
                        persona_identity = persona_path.read_text()
                    else:
                        public_path = data_dir() / f"public/personas/{active}/persona.txt"
                        if public_path.exists():
                            persona_identity = public_path.read_text()
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
        return persona_identity

    def _parse_xml_tools(self, xml_tool_pattern, response):
        """Parse XML-style tool calls from response text."""
        tool_matches = []
        xml_matches = xml_tool_pattern.findall(response)
        for xml_content in xml_matches:
            try:
                import json
                clean_content = xml_content.strip()
                
                if clean_content.startswith("```json"):
                    clean_content = clean_content[7:]
                elif clean_content.startswith("```"):
                    clean_content = clean_content[3:]
                if clean_content.endswith("```"):
                    clean_content = clean_content[:-3]
                
                clean_content = clean_content.strip()
                
                start = clean_content.find("{")
                end = clean_content.rfind("}")
                
                if start != -1 and end != -1:
                    json_str = clean_content[start:end+1]
                    
                    tool_data = None
                    try:
                        tool_data = json.loads(json_str)
                    except json.JSONDecodeError:
                        try:
                            tool_data = ast.literal_eval(json_str)
                        except Exception as e:
                            logger.warning(f"Suppressed {type(e).__name__}: {e}")
                    
                    if isinstance(tool_data, dict) and "name" in tool_data:
                        t_name = tool_data["name"]
                        t_args = tool_data.get("arguments", {})
                        arg_str_parts = []
                        if isinstance(t_args, dict):
                            for k, v in t_args.items():
                                if isinstance(v, str):
                                    safe_v = v.replace('"', '\\"')
                                    arg_str_parts.append(f'{k}="{safe_v}"')
                                else:
                                    arg_str_parts.append(f'{k}={v}')
                        arg_str = ", ".join(arg_str_parts)
                        tool_matches.append((t_name, arg_str))
            except Exception as json_err:
                logger.warning(f"Failed to parse XML tool call: {json_err}")
        return tool_matches

    async def _evaluate_final_answer(
        self, response, step, input_text, system_context, turn_history,
        reading_tracker, comprehension_check_done, tool_usage_counts,
        executed_tools_history, all_tool_outputs, request_scope,
        user_id, skip_defenses, images, _is_admin_user,
        conversation_context="",
    ):
        """
        Evaluate whether a no-tool response qualifies as the final answer.
        Returns the response text if accepted, "__CONTINUE__" if loop should continue, or None.
        """
        # GAMING FAST PATH
        if skip_defenses:
            logger.info(f"Final Answer (skip_defenses) at Step {step}.")
            return response
        
        # Anti-Laziness: Block if reading incomplete
        unfinished = reading_tracker.get_unfinished()
        if unfinished:
            logger.warning(f"Anti-laziness: Blocked final answer — {len(unfinished)} documents unfinished")
            return "__CONTINUE__"
        
        # Anti-Laziness: Comprehension Check
        if reading_tracker.has_reads() and not comprehension_check_done:
            logger.info(f"Comprehension check injected for {len(reading_tracker.get_all_read())} documents")
            return "__CONTINUE__"
        
        # PERSONA UPDATE BYPASS
        _persona_tools = {"update_persona", "update_identity"}
        if any(t in _persona_tools for t in tool_usage_counts):
            logger.info(f"Final Answer (persona update bypass) at Step {step}.")
            return response
        
        # Skeptic Audit — applies to ALL users equally (no admin bypass)
        logger.info(f"[Step {step}] Skeptic Audit starting for user {user_id}")
        skeptic_passed = True
        skeptic_block_reason = "Audit block"
        try:
            skeptic = self.bot.cerebrum.get_lobe("SuperegoLobe")
            if skeptic:
                safe_scope = request_scope or "PUBLIC"
                history_key = f"{user_id}_{safe_scope}" if user_id else f"system_{safe_scope}"
                user_history = self.user_tool_history[history_key]

                audit_res = await skeptic.get_ability("AuditAbility").audit_response(
                    input_text, response, all_tool_outputs,
                    session_history=user_history,
                    system_context=system_context,
                    images=images,
                    conversation_context=conversation_context
                )
                if not audit_res["allowed"]:
                    skeptic_passed = False
                    skeptic_block_reason = audit_res.get('reason', 'Unspecified block')
                    logger.info(f"[Step {step}] Skeptic BLOCKED response for user {user_id}: {skeptic_block_reason}")
                else:
                    logger.info(f"[Step {step}] Skeptic Audit PASSED for user {user_id}")
        except Exception as e:
            logger.error(f"Skeptic Audit Error: {e}")
        
        if skeptic_passed:
            # Circuit Breaker — applies to ALL users equally
            logger.info(f"[Step {step}] Integrity Check (Circuit Breaker) starting")
            is_honest, integrity_issue = True, ""
            try:
                skeptic_lobe = self.bot.cerebrum.get_lobe("SuperegoLobe")
                if skeptic_lobe:
                    is_honest, integrity_issue = skeptic_lobe.get_ability("AuditAbility").verify_response_integrity(response, executed_tools_history)
            except Exception as e:
                logger.error(f"Integrity Check Error: {e}")

            if not is_honest:
                logger.info(f"[Step {step}] Circuit Breaker TRIPPED — triggering regen: {integrity_issue}")
                return f"__CONTINUE__|Circuit Breaker: {integrity_issue}"
            else:
                logger.info(f"[Step {step}] All audits PASSED. Final Answer accepted.")
                return response
        
        # Skeptic blocked — inject guidance and continue
        return f"__CONTINUE__|{skeptic_block_reason}"

    # === Trace & Transparency (Delegated to CognitionTracer) ===
    
    def _save_trace(self, step, response, results, request_scope=None):
        """Save reasoning trace. Delegates to CognitionTracer."""
        from .trace import CognitionTracer
        tracer = CognitionTracer(self.bot)
        tracer.save_trace(step, response, results, request_scope)

    def _generate_fallback(self, history):
        """Extracts the last meaningful response if loop fails."""
        from .trace import CognitionTracer
        tracer = CognitionTracer(self.bot)
        return tracer.generate_fallback(history)

    async def _send_thought_to_mind(self, step: int, thought: str, request_scope: str = None):
        """Broadcasts reasoning step to Mind Channel for transparency."""
        from .trace import CognitionTracer
        tracer = CognitionTracer(self.bot)
        await tracer.send_thought_to_mind(step, thought, request_scope=request_scope)
