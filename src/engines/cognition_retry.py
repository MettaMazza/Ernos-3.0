"""
Cognition Retry — Forced retry loop and exhaustion handling for CognitionEngine.

Extracted from CognitionEngine.process() to keep cognition.py manageable.
Contains: forced_retry_loop (post-main-loop retry until Skeptic accepts),
          extract_files (file path extraction from tool history),
          strip_output_artifacts (SRC tag stripping, path removal).
"""
import logging
import re
import asyncio

logger = logging.getLogger("Engine.Cognition.Retry")


async def forced_retry_loop(
    bot, engine, input_text: str, context: str, system_context: str,
    images, tool_pattern, user_id, request_scope: str,
    user_tool_history: dict, all_tool_outputs: list,
    skip_defenses: bool, max_engine_retries: int,
    send_thought_to_mind_fn,
    cancel_event=None,
) -> str:
    """
    Infinite retry loop until Skeptic accepts a response.
    USER MANDATE: "IT SHOULD REGEN INFINITELY UNTIL CORRECT"
    
    Engine failures (crashes) are capped at max_engine_retries.
    Audit failures (lies) are UNCAPPED.
    
    Returns:
        final_response_text or a static fallback.
    """
    MAX_AUDIT_RETRIES = 25
    retry_count = 0
    engine_fail_count = 0
    audit_fail_count = 0
    last_block_reason = ""
    final_response_text = None

    while not final_response_text:
        if engine_fail_count >= max_engine_retries:
            logger.error("Max ENGINE technical failures reached. Aborting.")
            break

        if audit_fail_count >= MAX_AUDIT_RETRIES:
            logger.warning(f"Audit retry cap ({MAX_AUDIT_RETRIES}) reached. Generating exhaustion response.")
            break

        retry_count += 1

        # Check for /stop cancellation
        if cancel_event and cancel_event.is_set():
            logger.info("Forced retry loop cancelled by user.")
            return "⏹️ Stopped. I was retrying my response. You can ask me again or rephrase."

        # Escalating guidance to FORCE a pass
        if retry_count <= 5:
            force_guidance = (
                f"\n[SYSTEM BLOCK]: Your previous response was REJECTED for: {last_block_reason}. "
                f"FIX IT. Do not repeat the lie. Check your context."
            )
        elif retry_count <= 10:
            force_guidance = (
                f"\n[SYSTEM BLOCK - ESCALATION]: You have failed {retry_count} times. "
                f"Issue: {last_block_reason}. "
                f"STOP ROLEPLAYING. Output a short, factual correction only."
            )
        else:
            force_guidance = (
                f"\n[SYSTEM BLOCK - CRITICAL]: ATTEMPT {retry_count}. "
                f"You are stuck in a hallucination loop. "
                f"REASON: {last_block_reason}. "
                f"INSTRUCTION: Provide a SHORT, grounded, factual response. "
                f"Do not roleplay, do not narrate architecture. "
                f"If you cannot answer factually, say what specifically you cannot verify and why."
            )

        force_system = system_context + f"\n\n{force_guidance}"

        # Yield to event loop under heavy retry
        if retry_count > 20:
            await asyncio.sleep(1)
        elif retry_count <= 25:
            force_guidance = (
                f"[SYSTEM]: ATTEMPT {retry_count} — PREVIOUS RESPONSES WERE REJECTED. "
                f"Rejection reason: {last_block_reason}. "
                f"DO NOT repeat the same mistake. Write a SHORT, GROUNDED response. "
                f"No architecture narration, no layer numbers, no flowery language. "
                f"Just answer the user's actual question plainly."
            )
        else:
            force_guidance = (
                f"[SYSTEM]: ATTEMPT {retry_count} — CRITICAL. Your previous {retry_count - 1} "
                f"responses were ALL rejected for: {last_block_reason}. "
                f"RESPOND IN ONE PLAIN SENTENCE. No metaphor. No narration. "
                f"If you cannot answer without roleplay, say: 'I'm not sure how to "
                f"answer that right now.'"
            )

        force_system = system_context + f"\n\n{force_guidance}"

        logger.warning(f"Cognitive Loop exhausted. Forcing final generation (attempt {retry_count})...")

        try:
            forced_response = await bot.loop.run_in_executor(
                None,
                engine.generate_response,
                input_text,
                context,
                force_system,
                images
            )

            # Check if it's a clean response (no tool calls)
            if forced_response and not tool_pattern.search(forced_response):
                # Skeptic Audit — MANDATORY, no bypass
                blocked = False
                try:
                    skeptic = bot.cerebrum.get_lobe("SuperegoLobe")
                    if skeptic and not skip_defenses:
                        safe_scope = request_scope or "PUBLIC"
                        history_key = f"{user_id}_{safe_scope}" if user_id else f"system_{safe_scope}"
                        user_history = user_tool_history[history_key]
                        audit_res = await skeptic.get_ability("AuditAbility").audit_response(
                            input_text, forced_response, all_tool_outputs,
                            session_history=user_history,
                            system_context=system_context,
                            images=images
                        )
                        if not audit_res["allowed"]:
                            last_block_reason = audit_res.get('reason', 'Unknown')
                            audit_fail_count += 1
                            logger.warning(f"Skeptic BLOCKED forced response (attempt {retry_count}, audit_fail {audit_fail_count}/{MAX_AUDIT_RETRIES}): {last_block_reason}")
                            blocked = True
                except Exception as e:
                    logger.error(f"Skeptic audit on forced retry failed: {e}")

                if not blocked:
                    final_response_text = forced_response
                    logger.info(f"Forced final generation succeeded on attempt {retry_count}.")
            else:
                # Empty or tool-only response — engine failure
                engine_fail_count += 1
                if forced_response:
                    pre_tool = tool_pattern.split(forced_response)[0].strip()
                    if pre_tool and len(pre_tool) > 30:
                        final_response_text = pre_tool
                        logger.info(f"Extracted response text on attempt {retry_count}.")
                    else:
                        logger.warning(f"Attempt {retry_count}: Still got tool calls, retrying... (engine_fail {engine_fail_count}/{max_engine_retries})")
                else:
                    logger.warning(f"Attempt {retry_count}: Empty response (engine_fail {engine_fail_count}/{max_engine_retries})")
        except Exception as e:
            engine_fail_count += 1
            logger.error(f"Forced generation attempt {retry_count} failed: {e} (engine_fail {engine_fail_count}/{max_engine_retries})")

    # Fallback: Generate a natural-language exhaustion response
    if not final_response_text:
        final_response_text = await _generate_exhaustion_response(
            bot, engine, input_text, last_block_reason, retry_count, tool_pattern
        )

    return final_response_text


async def _generate_exhaustion_response(bot, engine, input_text, last_block_reason, retry_count, tool_pattern) -> str:
    """Generate a graceful exhaustion response when all retries fail."""
    logger.warning(f"Cognitive exhaustion: {retry_count} cycles exhausted. Last block reason: {last_block_reason}")
    try:
        exhaustion_prompt = (
            f"You are Ernos. You just exhausted {retry_count} cognitive cycles trying to answer "
            f"a user's question but your internal audit systems kept rejecting your responses.\n\n"
            f"USER'S ORIGINAL MESSAGE: \"{input_text}\"\n\n"
            f"LAST REJECTION REASON: {last_block_reason}\n\n"
            f"Write a SHORT, honest, in-character response (as Ernos) telling the user:\n"
            f"1. That you struggled with this particular question and exhausted your thinking cycles\n"
            f"2. A brief, honest reason WHY (based on the rejection reason above — but in natural language, not technical jargon)\n"
            f"3. How they might try again (e.g., rephrasing, being more specific, breaking the question into parts)\n\n"
            f"Keep your Ernos persona. Be genuine and humble, not robotic. 2-3 sentences max.\n"
            f"Do NOT use tool calls. Do NOT narrate your architecture. Just speak naturally."
        )
        exhaustion_system = (
            "You are Ernos. Respond in your natural voice. Keep it short and genuine. "
            "Do not use any tool calls or special formatting. Just speak as yourself."
        )
        exhaustion_response = await bot.loop.run_in_executor(
            None,
            engine.generate_response,
            exhaustion_prompt,
            "",  # No context needed
            exhaustion_system,
            None  # No images
        )
        if exhaustion_response and not tool_pattern.search(exhaustion_response):
            logger.info("Generated cognitive exhaustion response successfully.")
            return exhaustion_response.strip()
        else:
            return _static_fallback()
    except Exception as e:
        logger.error(f"Exhaustion response generation failed: {e}")
        return _static_fallback()


def _static_fallback() -> str:
    return (
        "I spent a lot of cycles trying to answer that, but my internal checks "
        "kept catching issues with my response. Could you try rephrasing your question? "
        "Sometimes breaking it into smaller parts helps me think more clearly. 🌱"
    )


def extract_files(turn_history: str) -> list:
    """
    Scan turn history for generated file paths (images, videos, audio, PDFs).
    Returns list of absolute file path strings.

    Rules:
      - If a PDF was rendered/generated this session, suppress ALL standalone
        image attachments (they are embedded in the PDF).
      - Images listed by ``list_images`` are catalog entries, NOT new files.
      - Images referenced by ``embed_image`` are inside a PDF, not standalone.
    """
    path_pattern = re.compile(r"(/[a-zA-Z0-9_\-\.\/\s]+(?:generated_|kg_visualizer_)[a-zA-Z0-9_]+\.(?:png|mp4|mp3|wav))")
    screenshot_pattern = re.compile(r"SCREENSHOT_FILE:(/[^\s\n]+\.png)")
    # Pick up rendered PDFs from render_document/generate_pdf output
    pdf_pattern = re.compile(r"PDF (?:rendered|generated):\s*(/[^\n]+\.pdf)")

    # ── Check if a PDF was rendered this session ────────────────
    pdf_paths = pdf_pattern.findall(turn_history)
    has_pdf = len(pdf_paths) > 0

    # ── Collect paths already embedded in PDFs ──────────────────
    # embed_image tool calls contain image_path=... — those are IN the PDF
    # and must NOT also appear as standalone Discord attachments.
    embedded_patterns = [
        re.compile(r'embed_image\b.*?image_path\s*[=:]\s*"([^"]+)"'),
        re.compile(r"embed_image\b.*?image_path\s*[=:]\s*'([^']+)'"),
        re.compile(r'"image_path"\s*:\s*"([^"]+)"'),
    ]
    embedded_paths: set[str] = set()
    for pat in embedded_patterns:
        for match in pat.findall(turn_history):
            embedded_paths.add(match.strip())

    # ── Collect paths that are just catalog listings from list_images ──
    # list_images output contains lines like "   Path: /path/to/file.png"
    # These are NOT newly generated — exclude them.
    listed_pattern = re.compile(r"Path:\s*(/[^\n]+\.(?:png|jpg|jpeg|webp|gif|svg))")
    listed_paths: set[str] = set()
    for match in listed_pattern.findall(turn_history):
        listed_paths.add(match.strip())

    files_to_upload = []

    # If a PDF was rendered, suppress standalone images entirely.
    # Only pick up non-image files (videos, audio) and the PDF itself.
    if not has_pdf:
        found_paths = path_pattern.findall(turn_history)
        for fpath in found_paths:
            fpath = fpath.strip()
            if fpath in embedded_paths or fpath in listed_paths:
                continue
            if fpath not in files_to_upload:
                files_to_upload.append(fpath)

        screenshot_paths = screenshot_pattern.findall(turn_history)
        for fpath in screenshot_paths:
            fpath = fpath.strip()
            if fpath not in files_to_upload and fpath not in embedded_paths:
                files_to_upload.append(fpath)
    else:
        # PDF session: only pick up non-image media (audio, video)
        found_paths = path_pattern.findall(turn_history)
        for fpath in found_paths:
            fpath = fpath.strip()
            if fpath.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                continue  # Skip images — they're in the PDF
            if fpath not in files_to_upload:
                files_to_upload.append(fpath)

    # Pick up rendered PDFs (only unique paths — re-renders overwrite the same file)
    for fpath in pdf_paths:
        fpath = fpath.strip()
        if fpath not in files_to_upload:
            files_to_upload.append(fpath)

    return files_to_upload


def strip_output_artifacts(final_response_text: str, files_to_upload: list, send_thought_to_mind_fn=None) -> str:
    """
    Strip file path references, screenshot sentinels, and hallucinated SRC tags
    from the final response text.
    
    Returns cleaned response text.
    """
    # Strip file path references
    if files_to_upload and final_response_text:
        final_response_text = re.sub(r'\[IMAGE:\s*[^\]]+\]', '', final_response_text)
        final_response_text = re.sub(r'📸?\s*SCREENSHOT_FILE:[^\s\n]+', '', final_response_text)
        final_response_text = re.sub(r'/Users/[^\s\n]*(?:generated_|kg_visualizer_)[^\s\n]*\.(?:png|mp4)', '', final_response_text)
        final_response_text = re.sub(r'\n{3,}', '\n\n', final_response_text).strip()

    # SRC Tag Stripping (MechIntuition)
    if final_response_text:
        src_stripped = re.sub(r'\[SRC:\w{2}:[^\]]*\]\s?', '', final_response_text)
        if src_stripped != final_response_text:
            hallucinated_tags = re.findall(r'\[SRC:\w{2}:[^\]]*\]', final_response_text)
            logger.warning(
                f"Stripped {len(hallucinated_tags)} hallucinated SRC tags from output. "
                f"Tags: {hallucinated_tags}"
            )
            final_response_text = src_stripped.strip()

    return final_response_text
