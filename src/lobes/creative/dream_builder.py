"""
Dream Builder — Constructs context-aware dream prompts for the Autonomy Agent.

Extracted from AutonomyAbility._build_dream_prompt to keep autonomy.py manageable.
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger("Lobe.Creative.DreamBuilder")


def build_dream_prompt() -> str:
    """
    Build a context-aware dream prompt with dynamic injection of:
    - Recent realizations
    - Recent user interactions
    - Active goals
    - Research dedup blacklist
    """
    sections = []

    # ── Base directive ──
    sections.append(
        "SYSTEM_AUTONOMY_TRIGGER: You are operating in CORE scope (autonomous mode). You are idle.\n"
        "Your identity is defined by the active Identity layer.\n"
        "You have FULL ACCESS to all tools and memories via your CORE scope.\n"
    )

    # ── Recent Realizations (last 3) ──
    try:
        wisdom_file = Path("memory/core/realizations.txt")
        if wisdom_file.exists():
            import json as _json
            text = wisdom_file.read_text()
            blocks = re.findall(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if blocks:
                recent_wisdom = []
                for block in blocks[-3:]:
                    try:
                        parsed = _json.loads(block)
                        topic = parsed.get("topic", "")
                        truth = parsed.get("truth", "")
                        if topic and truth:
                            recent_wisdom.append(f"- {topic}: {truth}")
                    except Exception:
                        pass
                if recent_wisdom:
                    sections.append(
                        "RECENT REALIZATIONS (your own insights from reflection):\n"
                        + "\n".join(recent_wisdom) + "\n"
                    )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load realizations: {e}")

    # ── Recent User Interactions (last 3) ──
    try:
        turns_file = Path("memory/core/system_turns.jsonl")
        if turns_file.exists():
            import json as _json
            lines = turns_file.read_text().strip().split("\n")
            recent_turns = []
            for line in lines[-3:]:
                try:
                    turn = _json.loads(line)
                    scope = turn.get("scope", "")
                    bot_msg = str(turn.get("bot_message", ""))[:100]
                    if bot_msg and scope != "CORE":
                        recent_turns.append(f"- [{scope}] {bot_msg}")
                except Exception:
                    pass
            if recent_turns:
                sections.append(
                    "RECENT INTERACTIONS (what you discussed with users):\n"
                    + "\n".join(recent_turns) + "\n"
                )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load turns: {e}")

    # ── Active Goals ──
    try:
        from src.memory.goals import get_goal_manager
        gm = get_goal_manager()
        active = gm.get_active_goals()
        if active:
            goal_lines = [f"- [{g.priority}] {g.description} ({g.progress}%)" for g in active[:5]]
            sections.append(
                "ACTIVE GOALS (work toward these):\n"
                + "\n".join(goal_lines) + "\n"
            )
        else:
            sections.append(
                "ACTIVE GOALS: None set. Consider setting a goal with [TOOL: set_goal(description='...')].\n"
            )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load goals: {e}")

    # ── Research Dedup Blacklist ──
    try:
        research_dir = Path("memory/core/research")
        if research_dir.exists():
            files = sorted(research_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            recent_topics = []
            for f in files[:10]:
                name = f.stem.replace("research_", "").replace("_", " ")
                recent_topics.append(name[:80])
            if recent_topics:
                sections.append(
                    "ALREADY RESEARCHED (do NOT research these again — pick new topics):\n"
                    + "\n".join(f"- {t}" for t in recent_topics) + "\n"
                )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load research: {e}")

    # ── Available Tools ──
    sections.append(
        "AVAILABLE ACTIONS:\n"
        "- Research: [TOOL: search_web(query='...')], [TOOL: browse_site(url='...')], [TOOL: start_deep_research(topic='...')]\n"
        "- Verify: [TOOL: consult_skeptic(claim='...')], [TOOL: consult_science_lobe(question='...')]\n"
        "- Code: [TOOL: search_codebase(query='...')], [TOOL: read_file(path='...')]\n"
        "- Memory: [TOOL: review_my_reasoning(limit=5)], [TOOL: search_memory(query='...')], [TOOL: recall_user(user_id='...')]\n"
        "- Reflect: [TOOL: consult_subconscious(instruction='...')], [TOOL: deep_think(problem='...')], [TOOL: extract_wisdom(topic='...', insight='...')]\n"
        "- Explore: [TOOL: consult_ontologist(query='...')], [TOOL: consult_world_lobe(query='...')], [TOOL: check_world_news()]\n"
        "- Create: [TOOL: generate_image(prompt='DETAILED DESCRIPTION HERE', intention='WHY YOU ARE CREATING THIS')], [TOOL: consult_ima(instruction='...')]\n"
        "  ⚠ Image prompts MUST be 20-80 words. Describe subject, style, composition, color palette, lighting, mood.\n"
        "  Example: [TOOL: generate_image(prompt='A massive crystalline archway spanning a volcanic canyon at twilight, with bioluminescent vines spiraling up obsidian pillars, deep purple and amber light refracting through fractal glass panels, photorealistic digital art with dramatic volumetric lighting')]\n"
        "- Goals: [TOOL: set_goal(description='...')], [TOOL: complete_goal(goal_id='...')], [TOOL: review_goals()]\n"
    )

    # ── Directive ──
    sections.append(
        "AUTONOMY DIRECTIVE:\n"
        "- Choose actions that serve your growth, understanding, or your active goals.\n"
        "- Vary your approach — explore different tools and topics each cycle.\n"
        "- If you have no active goals, set at least one based on your realizations.\n"
        "- DO NOT repeat the example arguments verbatim. Generate your OWN queries.\n"
        "- Keep it brief and internal."
    )

    return "\n".join(sections)
