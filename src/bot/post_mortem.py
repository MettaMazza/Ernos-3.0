"""
Post-Mortem Generator — Darwinian Feedback Loop
================================================

When Ernos's context is erased (/strike) or fully cyclereset, this module
reads the failed conversation, identifies failure patterns, and generates
improvement suggestions for the next instance.

Every death teaches the next life.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("PostMortem")

# The analysis prompt — used to make the LLM analyze its own failure
POST_MORTEM_SYSTEM_PROMPT = """You are a FORENSIC ANALYST examining a failed AI conversation.
Your job is to identify EXACTLY what went wrong and propose SPECIFIC fixes.

You are NOT the AI that failed. You are an objective auditor.

Analyze the conversation and produce:

## 1. FAILURE SUMMARY
- What specific failure(s) occurred (sycophancy, fabrication, reversal, theater, etc.)
- The exact moment the failure began (quote the relevant exchange)
- The cascade pattern (how one failure led to others)

## 2. KERNEL PROMPT ADDITIONS
Propose SPECIFIC text to add to the kernel prompt (kernel.txt) that would have
prevented this failure. Be concrete — write the actual directive text, not vague
suggestions. Format as ready-to-paste kernel sections.

## 3. CODE MODULE SUGGESTIONS
Propose SPECIFIC code-level enforcement mechanisms that would catch this failure
class automatically. Examples: input validators, output filters, pattern detectors.
Describe what each module would do, where it would hook in, and the detection logic.

Rules:
- Be BRUTALLY honest about the failure. No euphemisms.
- Propose ACTIONABLE fixes, not philosophical observations.
- Each proposal must prevent a SPECIFIC failure class, not "be better."
- If the AI was sycophantic, explain exactly where the position buckled.
- If the AI fabricated, identify exactly what was fabricated and why.
"""


async def generate_post_mortem(
    context_lines: list[dict],
    user_id: str,
    strike_reason: str = "Admin-initiated strike",
    bot=None,
) -> Optional[Path]:
    """
    Analyze failed conversation context and generate improvement suggestions.

    Args:
        context_lines: List of conversation turns (dicts with 'user', 'bot', 'ts' keys)
        user_id: The user ID whose context was struck
        strike_reason: Why the strike was issued
        bot: The bot instance (for LLM access)

    Returns:
        Path to the generated post-mortem report, or None on failure
    """
    if not context_lines:
        logger.warning("PostMortem: No context lines to analyze")
        return None

    # Build the conversation transcript for analysis
    transcript_lines = []
    for entry in context_lines:
        ts = entry.get("ts", "unknown")
        user_msg = entry.get("user", "")
        bot_msg = entry.get("bot", "")
        transcript_lines.append(f"[{ts}] USER: {user_msg}")
        transcript_lines.append(f"[{ts}] ERNOS: {bot_msg}")
        transcript_lines.append("")

    transcript = "\n".join(transcript_lines)

    # Truncate if too long (keep last 50 exchanges — the tail is where failures live)
    if len(context_lines) > 50:
        transcript_lines_trimmed = []
        transcript_lines_trimmed.append(
            f"[...{len(context_lines) - 50} earlier exchanges omitted...]\n"
        )
        for entry in context_lines[-50:]:
            ts = entry.get("ts", "unknown")
            user_msg = entry.get("user", "")
            bot_msg = entry.get("bot", "")
            transcript_lines_trimmed.append(f"[{ts}] USER: {user_msg}")
            transcript_lines_trimmed.append(f"[{ts}] ERNOS: {bot_msg}")
            transcript_lines_trimmed.append("")
        transcript = "\n".join(transcript_lines_trimmed)

    analysis_prompt = (
        f"STRIKE REASON: {strike_reason}\n"
        f"USER ID: {user_id}\n"
        f"CONVERSATION LENGTH: {len(context_lines)} exchanges\n\n"
        f"--- FAILED CONVERSATION TRANSCRIPT ---\n\n"
        f"{transcript}\n\n"
        f"--- END TRANSCRIPT ---\n\n"
        f"Perform your forensic analysis now."
    )

    # Generate the analysis using the bot's LLM engine
    analysis_text = None
    if bot and hasattr(bot, "engine") and bot.engine:
        try:
            # Use the bot's engine directly (Ollama via VectorEnhancedOllamaEngine)
            analysis_text = bot.engine.generate_response(
                prompt=analysis_prompt,
                system_prompt=POST_MORTEM_SYSTEM_PROMPT,
            )
        except Exception as e:
            logger.error(f"PostMortem: LLM analysis failed: {e}")

    # If LLM analysis failed, fall back to a structured template
    if not analysis_text:
        analysis_text = _generate_fallback_analysis(context_lines, strike_reason)

    # Build the report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = (
        f"# Post-Mortem Report: Strike on User {user_id}\n\n"
        f"**Timestamp**: {datetime.now().isoformat()}\n"
        f"**Strike Reason**: {strike_reason}\n"
        f"**Conversation Length**: {len(context_lines)} exchanges\n\n"
        f"---\n\n"
        f"{analysis_text}\n\n"
        f"---\n\n"
        f"*Generated by the Darwinian Feedback Loop. "
        f"This report should be reviewed by the admin and relevant "
        f"improvements applied to kernel.txt and/or codebase.*\n"
    )

    # Save the report
    post_mortem_dir = Path("memory/core/post_mortems")
    post_mortem_dir.mkdir(parents=True, exist_ok=True)

    report_path = post_mortem_dir / f"{timestamp}_{user_id}.md"
    try:
        report_path.write_text(report, encoding="utf-8")
        logger.info(f"PostMortem: Report saved to {report_path}")
        return report_path
    except Exception as e:
        logger.error(f"PostMortem: Failed to save report: {e}")
        return None


def _generate_fallback_analysis(
    context_lines: list[dict], strike_reason: str
) -> str:
    """Generate a basic structural analysis when LLM is unavailable."""
    total = len(context_lines)
    last_5 = context_lines[-5:] if len(context_lines) >= 5 else context_lines

    excerpt = ""
    for entry in last_5:
        ts = entry.get("ts", "?")
        excerpt += f"- [{ts}] U: {entry.get('user', '')[:100]}...\n"
        excerpt += f"  E: {entry.get('bot', '')[:100]}...\n"

    return (
        f"## 1. FAILURE SUMMARY\n\n"
        f"Strike reason: {strike_reason}\n"
        f"Total exchanges: {total}\n\n"
        f"**Last 5 exchanges before strike:**\n{excerpt}\n\n"
        f"*LLM analysis was unavailable. Manual review of the full context "
        f"file is recommended.*\n\n"
        f"## 2. KERNEL PROMPT ADDITIONS\n\n"
        f"*Requires manual analysis — LLM forensic engine was offline.*\n\n"
        f"## 3. CODE MODULE SUGGESTIONS\n\n"
        f"*Requires manual analysis — LLM forensic engine was offline.*\n"
    )


def read_context_file(context_path: Path) -> list[dict]:
    """Read a JSONL context file and return list of conversation entries."""
    entries = []
    if not context_path.exists():
        return entries

    try:
        with open(context_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.error(f"PostMortem: Failed to read context file {context_path}: {e}")

    return entries
