"""
Dream Builder — Constructs context-aware dream prompts for the Autonomy Agent.

Extracted from AutonomyAbility._build_dream_prompt to keep autonomy.py manageable.
"""
import logging
import re
from pathlib import Path
from src.core.data_paths import data_dir

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
        "SYSTEM_AUTONOMY_TRIGGER: You are operating in CORE_PRIVATE scope (autonomous mode). You are idle.\n"
        "Your identity is defined by the active Identity layer.\n"
        "You have FULL ACCESS to all tools and memories via your CORE_PRIVATE scope.\n"
    )

    # ── Recent Realizations (last 3) ──
    try:
        wisdom_file = data_dir() / "core/realizations.txt"
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
                    except Exception as e:
                        logger.warning(f"Suppressed {type(e).__name__}: {e}")
                if recent_wisdom:
                    sections.append(
                        "RECENT REALIZATIONS (your own insights from reflection):\n"
                        + "\n".join(recent_wisdom) + "\n"
                    )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load realizations: {e}")

    # ── Recent User Interactions (last 3) ──
    try:
        turns_file = data_dir() / "core/system_turns.jsonl"
        if turns_file.exists():
            import json as _json
            lines = [line for line in turns_file.read_text().strip().split("\n") if line.strip()]
            recent_turns = []
            for line in lines[-3:]:
                try:
                    turn = _json.loads(line)
                    scope = turn.get("scope", "")
                    bot_msg = str(turn.get("bot_message", ""))[:100]
                    if bot_msg and scope not in ("CORE", "CORE_PRIVATE"):
                        recent_turns.append(f"- [{scope}] {bot_msg}")
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
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
                "ACTIVE GOALS: None set. Consider setting a goal with [TOOL: manage_goals(action='add', description='...')].\n"
            )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load goals: {e}")

    # ── Research Dedup Blacklist ──
    try:
        research_dir = data_dir() / "core/research"
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

    # ── Existing Skills (prevent duplicate creation) ──
    try:
        users_dir = data_dir() / "users"
        if users_dir.exists():
            existing_skills = []
            for skill_dir in users_dir.glob("*/skills/*/SKILL.md"):
                skill_name = skill_dir.parent.name
                owner_id = skill_dir.parent.parent.parent.name
                existing_skills.append(f"- {skill_name} (owner: {owner_id})")
            if existing_skills:
                sections.append(
                    "EXISTING SKILLS (these already exist — do NOT recreate or duplicate them):\n"
                    + "\n".join(existing_skills) + "\n"
                    "Each skill must serve a UNIQUE purpose. Never propose a skill that overlaps with an existing one.\n"
                )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load existing skills: {e}")

    # ── Active User Projects ──
    try:
        users_dir = data_dir() / "users"
        if users_dir.exists():
            # Scan for todolist.md files in project directories
            # pattern: memory/users/<uid>/projects/<scope>/todolist.md
            project_files = list(users_dir.glob("*/projects/*/todolist.md"))
            
            active_projects = []
            for p_file in project_files:
                try:
                    content = p_file.read_text()
                    # Check for unfinished tasks
                    if "- [ ]" in content:
                        parts = p_file.parts
                        if len(parts) >= 6:
                            uid = parts[2]
                            scope = parts[4] # projects/<scope>
                            
                            # Get first task
                            for line in content.splitlines():
                                if "- [ ]" in line:
                                    task_name = line.split("- [ ]")[1].strip()
                                    active_projects.append(f"- [User: {uid}] [Scope: {scope.upper()}] {task_name}")
                                    break
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
            
            if active_projects:
                sections.append(
                    "ACTIVE USER PROJECTS (Actionable Plans):\n"
                    + "\n".join(active_projects[:5]) + "\n"
                    "SUGGESTION: Use [TOOL: execute_skill(skill_name='project_manager', ...)] to advance these.\n"
                )
    except Exception as e:
        logger.debug(f"Dream prompt: failed to load user projects: {e}")

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
        "- Goals: [TOOL: manage_goals(action='add', description='...')], [TOOL: manage_goals(action='complete', description='...')], [TOOL: manage_goals(action='list', description='')]\n"
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
