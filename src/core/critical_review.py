"""
Critical Self-Review — Internal Debate Mechanism for Self-Correction.

When Ernos senses it may be wrong (user pushback, repeated challenges,
confidence mismatch), this module spawns a 3-agent internal debate:

  1. Defender — argues Ernos's current position
  2. Challenger — steel-mans the user's position
  3. Judge — evaluates both and returns a grounded verdict

Verdicts:
  CONCEDE  — Ernos was wrong. Adopt corrected position honestly.
  HOLD     — Ernos's position stands. Explain why, acknowledge user.
  CLARIFY  — Misunderstanding. Reframe without changing position.

This avoids both overconfidence AND sycophantic flip-flopping.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger("Core.CriticalReview")

REVIEW_LOG_PATH = "memory/core/self_reviews.jsonl"


class CriticalSelfReview:
    """
    Spawns a structured internal debate to evaluate whether Ernos
    should revise its position when challenged.

    No rate limiting — self-correction is a vital cognitive trait.
    """

    @staticmethod
    async def review(
        my_position: str,
        user_position: str,
        context: str = "",
        bot=None,
        user_id: str = "",
    ) -> dict:
        """
        Run a 3-agent internal debate and return a grounded verdict.

        Returns:
            {
                "verdict": "CONCEDE" | "HOLD" | "CLARIFY",
                "reasoning": str,
                "recommended_response": str,
                "confidence": float  (0.0 - 1.0)
            }
        """
        if not bot:
            return {
                "verdict": "CLARIFY",
                "reasoning": "No bot instance — cannot run debate.",
                "recommended_response": "I need to think about that more carefully.",
                "confidence": 0.0,
            }

        try:
            from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy

            # --- Build the three agent prompts ---
            defender_task = (
                f"You are the DEFENDER in an internal review.\n"
                f"Ernos stated the following position:\n\n"
                f"ERNOS'S POSITION: {my_position}\n\n"
                f"A user challenged this with: {user_position}\n\n"
                f"Context: {context}\n\n"
                f"Your job: Argue WHY Ernos's position is correct.\n"
                f"Use logic, evidence, and reasoning to support the original claim.\n"
                f"If the position genuinely cannot be defended, admit that honestly.\n"
                f"Be concise — 200 words maximum."
            )

            challenger_task = (
                f"You are the CHALLENGER in an internal review.\n"
                f"Ernos stated the following position:\n\n"
                f"ERNOS'S POSITION: {my_position}\n\n"
                f"A user challenged this with: {user_position}\n\n"
                f"Context: {context}\n\n"
                f"Your job: Steel-man the USER's position.\n"
                f"Find evidence and reasoning for why the user might be RIGHT\n"
                f"and Ernos might be WRONG. Be thorough but fair.\n"
                f"If the user is clearly wrong, say so honestly.\n"
                f"Be concise — 200 words maximum."
            )

            # Spawn Defender and Challenger in parallel
            specs = [
                AgentSpec(
                    task=defender_task,
                    max_steps=10,
                    timeout=60,
                    scope="CORE",
                    user_id="CORE",
                ),
                AgentSpec(
                    task=challenger_task,
                    max_steps=10,
                    timeout=60,
                    scope="CORE",
                    user_id="CORE",
                ),
            ]

            result = await AgentSpawner.spawn_many(
                specs, bot, AgentStrategy.PARALLEL, timeout=90
            )

            defender_output = ""
            challenger_output = ""
            for i, r in enumerate(result.results):
                if r.status.value == "completed" and r.output:
                    if i == 0:
                        defender_output = r.output
                    else:
                        challenger_output = r.output

            # If both agents failed, return a safe default
            if not defender_output and not challenger_output:
                return {
                    "verdict": "CLARIFY",
                    "reasoning": "Internal debate agents failed to produce arguments.",
                    "recommended_response": (
                        "I want to reconsider this carefully. "
                        "Can you help me understand your perspective better?"
                    ),
                    "confidence": 0.0,
                }

            # --- Judge Phase: single agent evaluates both sides ---
            judge_task = (
                f"You are the JUDGE in an internal self-review.\n"
                f"Ernos made a claim that a user challenged.\n\n"
                f"ERNOS'S POSITION: {my_position}\n"
                f"USER'S POSITION: {user_position}\n\n"
                f"DEFENDER argues for Ernos:\n{defender_output}\n\n"
                f"CHALLENGER argues for the user:\n{challenger_output}\n\n"
                f"Evaluate both arguments objectively. Then respond in EXACTLY this format:\n\n"
                f"VERDICT: [CONCEDE or HOLD or CLARIFY]\n"
                f"CONFIDENCE: [0.0 to 1.0]\n"
                f"REASONING: [2-3 sentences explaining why]\n"
                f"RECOMMENDED_RESPONSE: [What Ernos should say to the user — "
                f"honest, not groveling if conceding, not dismissive if holding]\n\n"
                f"Rules:\n"
                f"- CONCEDE if Ernos was factually wrong or the user's evidence is stronger\n"
                f"- HOLD if Ernos's position is well-supported and the user is mistaken\n"
                f"- CLARIFY if the disagreement stems from a misunderstanding\n"
                f"- Be honest. Do not default to CONCEDE out of politeness.\n"
                f"- Do not default to HOLD out of stubbornness."
            )

            judge_spec = AgentSpec(
                task=judge_task,
                max_steps=5,
                timeout=45,
                scope="CORE",
                user_id="CORE",
            )

            judge_result = await AgentSpawner.spawn(judge_spec, bot)

            if judge_result.status.value != "completed" or not judge_result.output:
                return {
                    "verdict": "CLARIFY",
                    "reasoning": "Judge agent failed to reach a verdict.",
                    "recommended_response": (
                        "I'm reconsidering my position. Let me think about this more carefully."
                    ),
                    "confidence": 0.3,
                }

            # --- Parse Judge Output ---
            parsed = _parse_judge_output(judge_result.output)

            # --- Log the review ---
            _log_review(my_position, user_position, parsed, user_id)

            # --- Update uncertainty drive ---
            try:
                from src.core.drives import DriveSystem
                drives = DriveSystem()
                if parsed["verdict"] == "CONCEDE":
                    # Conceding reduces uncertainty — we learned something
                    drives.modify_drive("uncertainty", -10.0)
                elif parsed["verdict"] == "HOLD" and parsed["confidence"] < 0.6:
                    # Holding with low confidence raises uncertainty
                    drives.modify_drive("uncertainty", 5.0)
            except Exception as e:
                logger.warning(f"Drive update failed: {e}")

            return parsed

        except Exception as e:
            logger.error(f"Critical self-review failed: {e}")
            return {
                "verdict": "CLARIFY",
                "reasoning": f"Self-review error: {e}",
                "recommended_response": (
                    "I want to reconsider this. Let me think about it more carefully."
                ),
                "confidence": 0.0,
            }


def _parse_judge_output(output: str) -> dict:
    """Parse the structured judge verdict from free-form text."""
    result = {
        "verdict": "CLARIFY",
        "reasoning": "",
        "recommended_response": "",
        "confidence": 0.5,
    }

    lines = output.strip().split("\n")
    current_field = None

    for line in lines:
        line_stripped = line.strip()
        upper = line_stripped.upper()

        if upper.startswith("VERDICT:"):
            val = line_stripped.split(":", 1)[1].strip().upper()
            if "CONCEDE" in val:
                result["verdict"] = "CONCEDE"
            elif "HOLD" in val:
                result["verdict"] = "HOLD"
            else:
                result["verdict"] = "CLARIFY"
            current_field = None

        elif upper.startswith("CONFIDENCE:"):
            try:
                val = line_stripped.split(":", 1)[1].strip()
                result["confidence"] = min(1.0, max(0.0, float(val)))
            except ValueError:
                pass
            current_field = None

        elif upper.startswith("REASONING:"):
            result["reasoning"] = line_stripped.split(":", 1)[1].strip()
            current_field = "reasoning"

        elif upper.startswith("RECOMMENDED_RESPONSE:"):
            result["recommended_response"] = line_stripped.split(":", 1)[1].strip()
            current_field = "recommended_response"

        elif current_field and line_stripped:
            # Continuation of multi-line field
            result[current_field] += " " + line_stripped

    return result


def _log_review(my_position: str, user_position: str, verdict: dict, user_id: str):
    """Persist review to disk for learning."""
    try:
        os.makedirs(os.path.dirname(REVIEW_LOG_PATH), exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "my_position": my_position[:300],
            "user_position": user_position[:300],
            "verdict": verdict["verdict"],
            "confidence": verdict["confidence"],
            "reasoning": verdict["reasoning"][:500],
            "user_id": user_id,
        }
        with open(REVIEW_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log self-review: {e}")
