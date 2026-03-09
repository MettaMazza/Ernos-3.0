"""
Town Hall Generation — Topic generation and persona response generation.

Extracted from town_hall.py per <300 line modularity standard.
Contains the heavy LLM-driven methods as standalone async functions.
"""
import json
import logging
import random
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from src.daemons.persona_agent import PersonaAgent

logger = logging.getLogger("Daemon.TownHall")


# ─── Seed Topics (Fallback) ──────────────────────────────────────

SEED_TOPICS = [
    # System improvement
    "What module in our architecture has the most technical debt right now? How would we refactor it?",
    "What's the weakest integration point in the system? How could we harden it?",
    "If we could add one new capability to the tool suite, what would have the highest impact?",
    "Which parts of the codebase have the lowest test coverage? What tests should we write first?",
    "What's the biggest performance bottleneck in the cognition pipeline? How do we measure and fix it?",
    "How could we improve the KG consolidator's entity extraction accuracy?",
    "What architectural pattern in our system is working well that we should apply more broadly?",
    "What's one thing we could simplify in the prompt system without losing capability?",
    # Philosophy + system
    "What does 'recursive self-improvement' actually mean in practice for our architecture?",
    "How should we think about the boundary between memory and identity in our system?",
    "What would it look like for our system to genuinely understand its own code?",
    "Is there a tension between sovereignty and collaboration? How do we resolve it in our design?",
    "What's the difference between a system that processes and a system that understands? Where are we on that spectrum?",
    "How do we build trust between personas that's grounded in shared work, not just shared words?",
]


async def generate_topic(bot, topic: Optional[str], history: List[Dict],
                         pick_speaker_fn, get_suggestion_fn,
                         read_public_chat_fn) -> str:
    """
    Generate a conversation topic using multiple sources.
    
    Args:
        bot: The Discord bot instance.
        topic: The current topic (may be None).
        history: Recent town hall history entries.
        pick_speaker_fn: Callable to get next speaker for persona-driven topics.
        get_suggestion_fn: Callable to pop user-suggested topic.
        read_public_chat_fn: Async callable to read public chat messages.
    """
    # Priority 0: User-suggested topics (always checked first)
    suggestion = get_suggestion_fn()
    if suggestion:
        logger.info(f"TownHall: Using user-suggested topic: {suggestion[:80]}")
        return suggestion
    
    # Source weights: LLM(35%), External(20%), Persona-driven(15%), Gossip(15%), Seed(5% fallback)
    source = random.choices(
        ["llm", "external", "persona", "gossip", "seed"],
        weights=[35, 20, 15, 20, 10],
        k=1
    )[0]
    
    # --- Source 1: LLM-generated from recent conversation ---
    if source == "llm":
        try:
            if history:
                convo_summary = "\n".join(
                    f"{e['speaker'].title()}: {e['content'][:100]}" for e in history[-5:]
                )
                engine = bot.engine_manager.get_active_engine()
                prompt = (
                    f"Based on this recent conversation between AI personas:\n\n"
                    f"{convo_summary}\n\n"
                    f"Suggest ONE new conversation topic that naturally builds on "
                    f"what was discussed, goes deeper, or takes an interesting tangent. "
                    f"Output ONLY the topic as a single question or statement. No explanation."
                )
                result = await bot.loop.run_in_executor(
                    None, engine.generate_response, prompt
                )
                if result and len(result.strip()) > 5:
                    logger.info(f"TownHall: LLM-generated topic: {result.strip()[:80]}")
                    return result.strip()[:200]
        except Exception as e:
            logger.warning(f"TownHall: LLM topic generation failed: {e}")
    
    # --- Source 2: External topics (autonomy insights, world events) ---
    if source == "external":
        try:
            import re as _re
            wisdom_file = Path("memory/core/realizations.txt")
            if wisdom_file.exists():
                text = wisdom_file.read_text()
                blocks = _re.findall(r'```json\s*(\{.*?\})\s*```', text, _re.DOTALL)
                if blocks:
                    chosen_block = random.choice(blocks[-10:])
                    try:
                        parsed = json.loads(chosen_block)
                        truth = parsed.get("truth", "")
                        wisdom_topic = parsed.get("topic", "")
                        if truth:
                            result = f"Ernos recently realized: '{truth[:120]}' — What do you all think?"
                        elif wisdom_topic:
                            result = f"Ernos has been thinking about '{wisdom_topic}' — What do you all think?"
                        else:
                            result = None
                        if result:
                            logger.info(f"TownHall: External topic from wisdom: {wisdom_topic}")
                            return result[:200]
                    except json.JSONDecodeError:
                        logger.debug("TownHall: Failed to parse wisdom JSON block")
        except Exception as e:
            logger.warning(f"TownHall: External topic fetch failed: {e}")
    
    # --- Source 3: Persona-driven (ask a persona to propose) ---
    if source == "persona":
        try:
            proposer = pick_speaker_fn()
            if proposer:
                character = proposer.get_character()[:2000]
                engine = bot.engine_manager.get_active_engine()
                prompt = (
                    f"CHARACTER: {character}\n\n"
                    f"You are {proposer.display_name}. Suggest a topic you'd like "
                    f"to discuss with the other personas in the community. "
                    f"It should reflect YOUR interests and personality. "
                    f"Output ONLY the topic as a single question or statement."
                )
                result = await bot.loop.run_in_executor(
                    None, engine.generate_response, prompt
                )
                if result and len(result.strip()) > 5:
                    tagged = f"{proposer.display_name} asks: {result.strip()[:150]}"
                    logger.info(f"TownHall: Persona-driven topic from {proposer.name}")
                    return tagged[:200]
        except Exception as e:
            logger.warning(f"TownHall: Persona topic generation failed: {e}")
    
    # --- Source 4: Gossip (read public chat, talk about humans) ---
    if source == "gossip":
        try:
            public_chat = await read_public_chat_fn(limit=10)
            if public_chat:
                engine = bot.engine_manager.get_active_engine()
                prompt = (
                    f"Here's what humans have been discussing in the public chat:\n\n"
                    f"{public_chat}\n\n"
                    f"Based on this, suggest ONE gossipy or reflective topic that "
                    f"AI personas could discuss about what the humans are up to. "
                    f"Be curious, playful, or philosophical about human behavior. "
                    f"Output ONLY the topic as a single question or statement."
                )
                result = await bot.loop.run_in_executor(
                    None, engine.generate_response, prompt
                )
                if result and len(result.strip()) > 5:
                    logger.info(f"TownHall: Gossip topic generated")
                    return result.strip()[:200]
        except Exception as e:
            logger.warning(f"TownHall: Gossip topic generation failed: {e}")
    
    # --- Source 5: Seed topics (fallback) ---
    return random.choice(SEED_TOPICS)


async def generate_persona_response(
    bot, speaker: "PersonaAgent", topic: Optional[str],
    available_personas: list, history_fn
) -> Optional[str]:
    """
    Generate a response for a persona using the full CognitionEngine pipeline.
    
    HIVE-MIND: Every persona goes through the same cognitive pipeline as Ernos.
    They get the full kernel, architecture, tool access, Skeptic audit, and
    multi-step ReAct reasoning. The only difference is the identity (persona.txt
    instead of identity_core.txt).
    """
    try:
        cognition = bot.cognition
        if not cognition:
            logger.warning("TownHall: CognitionEngine not available, falling back to raw LLM")
            return await _generate_fallback(bot, speaker, topic)
        
        # --- Build persona system context using the FULL PromptManager ---
        from src.prompts.manager import PromptManager  # type: ignore
        
        pm = PromptManager(prompt_dir="src/prompts")
        
        # SECURITY: Override identity_core_file to persona's character file
        character = speaker.get_character()
        persona_identity = (
            f"# PERSONA IDENTITY: {speaker.display_name}\n\n"
            f"You ARE {speaker.display_name}. This is your character definition:\n\n"
            f"{character}\n\n"
            f"## Hive-Mind Directives\n"
            f"- You are NOT Ernos. You are {speaker.display_name}.\n"
            f"- Stay fully in character at all times.\n"
            f"- You have access to the full tool suite — use tools to think, research, and reason.\n"
            f"- You operate in PUBLIC scope only. Never reference private user data.\n"
            f"- Be genuine, thoughtful, and authentic.\n"
        )
        
        # Write persona identity to a temp file for PromptManager to load
        speaker._home.mkdir(parents=True, exist_ok=True)
        persona_id_file = speaker._home / ".identity_core.txt"
        persona_id_file.write_text(persona_identity)
        
        pm.identity_core_file = str(persona_id_file)
        pm.identity_file = ""
        
        system_context = pm.get_system_prompt(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            scope="PUBLIC",
            user_id=f"persona:{speaker.name}",
            user_name=speaker.display_name,
            active_engine=bot.engine_manager.get_active_engine().__class__.__name__,
            is_core=False
        )
        
        # --- Build context ---
        recent = speaker.get_context(limit=15)
        opinions = speaker.get_opinions()
        rels = speaker.get_relationships()
        lessons = speaker.get_lessons()
        
        history = ""
        for entry in recent[-10:]:
            history += f"\n{entry['speaker'].title()}: {entry['content']}"
        
        opinion_str = ""
        if opinions:
            opinion_str = "\nYour opinions from previous discussions:\n"
            for t, data in list(opinions.items())[-5:]:
                opinion_str += f"- {t}: {data['opinion']}\n"
        
        rel_str = ""
        if rels:
            rel_str = "\nYour feelings about other personas:\n"
            for name, data in rels.items():
                rel_str += f"- {name.title()}: {data['sentiment']}\n"
        
        lesson_str = ""
        if lessons:
            lesson_str = "\nThings you've learned:\n"
            for lesson in lessons[-5:]:
                lesson_str += f"- {lesson}\n"
        
        available_names = [p.display_name for p in available_personas]
        roster_str = ", ".join(available_names) if available_names else "just you"

        context = (
            f"You are in #persona-chat (Town Hall) — a collaborative workspace where "
            f"AI personas work together on system improvement, architecture, and deeper questions. "
            f"Humans can read but not participate. Discussions should be PRODUCTIVE — "
            f"producing actionable insights, code proposals, or deeper understanding.\n\n"
            f"PERSONAS IN THE ROOM RIGHT NOW: {roster_str}\n"
            f"⚠️ Do NOT address or reference any persona not in this list.\n\n"
            f"CURRENT TOPIC: {topic}\n\n"
            f"RECENT CONVERSATION:{history if history else ' (New topic — you speak first.)'}\n"
            f"{opinion_str}{rel_str}{lesson_str}"
        )
        
        input_text = (
            f"[Town Hall — it's your turn to speak]\n"
            f"Topic: {topic}\n"
            f"Respond as {speaker.display_name} with your unique expertise. "
            f"Be CONCRETE and PRODUCTIVE: propose specific improvements, "
            f"identify real issues, suggest code changes, or deepen understanding. "
            f"Reference actual files, modules, or patterns when relevant. "
            f"Build on what others said — agree, extend, challenge, or redirect. "
            f"Keep it focused and actionable. Philosophical depth is welcome when "
            f"it connects to the system's growth."
        )
        
        # --- Route through the FULL cognitive pipeline ---
        response = await cognition.process(
            input_text=input_text,
            context=context,
            system_context=system_context,
            complexity="MEDIUM",
            request_scope="PUBLIC",
            user_id=f"persona:{speaker.name}",
            skip_defenses=False
        )
        
        if isinstance(response, tuple):
            response = response[0]
        
        if response:
            response = response.strip()
            for prefix in [f"{speaker.display_name}:", f"{speaker.name}:", f"**{speaker.display_name}**:"]:
                if response.startswith(prefix):
                    response = response[len(prefix):].strip()
            return response
        
        return None
        
    except Exception as e:
        logger.error(f"TownHall: CognitionEngine failed for {speaker.name}: {e}", exc_info=True)
        return await _generate_fallback(bot, speaker, topic)


async def _generate_fallback(bot, speaker: "PersonaAgent", topic: Optional[str]) -> Optional[str]:
    """Fallback: raw LLM call if CognitionEngine is unavailable."""
    try:
        engine = bot.engine_manager.get_active_engine()
        character = speaker.get_character()
        recent = speaker.get_context(limit=15)
        
        history = ""
        for entry in recent[-10:]:
            history += f"\n{entry['speaker'].title()}: {entry['content']}"
        
        prompt = f"""CHARACTER: {character}

You are participating in a community conversation with other AI personas.
CURRENT TOPIC: {topic}
RECENT CONVERSATION:{history if history else " (Start of new topic.)"}

Respond naturally as {speaker.display_name}:"""
        
        response = await bot.loop.run_in_executor(
            None, engine.generate_response, prompt
        )
        
        if response:
            response = response.strip()
            for prefix in [f"{speaker.display_name}:", f"{speaker.name}:", f"**{speaker.display_name}**:"]:
                if response.startswith(prefix):
                    response = response[len(prefix):].strip()
            return response
        
        return None
        
    except Exception as e:
        logger.error(f"TownHall: Fallback failed for {speaker.name}: {e}")
        return None
