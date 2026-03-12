"""
Lobe Tools Router (The Bridge).
Exposes the specific Capabilities of the Cerebrum as callable tools for the Kernel.
"""
from .registry import ToolRegistry
import logging
import asyncio

logger = logging.getLogger("Tools.Lobes")

def _get_bot():
    """Resolve the bot instance via the globals module."""
    from src.bot import globals
    return globals.bot

def _safe_get_ability(bot, lobe_name: str, ability_name: str):
    """Null-safe lobe→ability lookup. Returns (ability, None) or (None, error_str)."""
    lobe = bot.cerebrum.get_lobe(lobe_name)
    if not lobe:
        return None, f"Error: {lobe_name} not loaded."
    ability = lobe.get_ability(ability_name)
    if not ability:
        return None, f"Error: {ability_name} not found in {lobe_name}."
    return ability, None

# --- Strategy Tools ---

# --- Strategy Tools ---

@ToolRegistry.register(name="consult_gardener_lobe", description="Code health analysis.")
async def consult_gardener_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("path") or kwargs.get("code") or "Analyze current codebase health"
    ability, err = _safe_get_ability(bot, "StrategyLobe", "GardenerAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(
    name="maintain_knowledge_graph",
    description=(
        "Run KG maintenance operations. "
        "Modes: 'connect' (discover and create missing relationships between under-connected nodes), "
        "'refine' (deduplicate near-identical nodes), "
        "'full' (refine then connect). "
        "Args: mode (str — 'connect', 'refine', or 'full', default 'connect')."
    ),
)
async def maintain_knowledge_graph(mode: str = "connect", **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "StrategyLobe", "GardenerAbility")
    if err: return err

    if mode == "refine":
        return await ability.refine_graph()
    elif mode == "full":
        refine_result = await ability.refine_graph()
        connect_result = await ability.connect_graph()
        return f"{refine_result}\n\n---\n\n{connect_result}"
    else:  # default: connect
        return await ability.connect_graph()

@ToolRegistry.register(name="consult_architect_lobe", description="High-level planning.")
async def consult_architect_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("plan") or kwargs.get("design") or "Review current architecture"
    ability, err = _safe_get_ability(bot, "StrategyLobe", "ArchitectAbility")
    if err: return err
    return await ability.execute(instruction)

# Alias for consult_architect_lobe - LLM sometimes uses this name
@ToolRegistry.register(name="consult_planning_lobe", description="High-level planning and strategy.")
async def consult_planning_lobe(instruction: str = None, **kwargs) -> str:
    return await consult_architect_lobe(instruction, **kwargs)

@ToolRegistry.register(name="consult_project_lead", description="Project tracking.")
async def consult_project_lead(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("task") or kwargs.get("status") or "Get project status"
    ability, err = _safe_get_ability(bot, "StrategyLobe", "ProjectLeadAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="execute_technical_plan", description="Execute a multi-step technical plan (e.g. refactor, feature implementation).")
def execute_technical_plan(goal: str, **kwargs) -> str:
    """Deprecated: Routes to plan_task for backward compatibility."""
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Security context missing (no user_id)."

    # Route to the new task tracker
    from src.tools.task_tracker import plan_task
    return (
        f"⚠️ execute_technical_plan is deprecated. Use plan_task instead.\n\n"
        f"To start this plan, call:\n"
        f"  plan_task(goal=\"{goal}\", steps=\"step1|step2|step3\")\n\n"
        f"Break down '{goal}' into specific steps first."
    )

@ToolRegistry.register(name="propose_prompt_update", description="Propose a modification to the system prompts. Args: prompt_file, section, current_text, proposed_text, rationale (why), cause (trigger event), operation (replace/append/insert/delete).")
async def propose_prompt_update(prompt_file: str, section: str, current_text: str, proposed_text: str, rationale: str, operation: str = "replace", cause: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    
    tuner, err = _safe_get_ability(bot, "StrategyLobe", "PromptTunerAbility")
    if err: return err
    
    # Ensure arguments are clean
    if not prompt_file:
        return "Error: Missing required argument (prompt_file)."
    if operation == "delete" and not current_text:
        return "Error: 'delete' operation requires current_text (the text to remove)."
    if operation in ("replace", "append", "insert") and not proposed_text:
        return "Error: Operation requires proposed_text."

    result = tuner.propose_modification(prompt_file, section, current_text, proposed_text, rationale, operation=operation, cause=cause)
    
    # Notify Admin Channel
    op_emoji = {"replace": "✏️", "append": "➕", "insert": "📌", "delete": "🗑️"}.get(operation, "📝")
    try:
        channel_id = 1471227259799994460
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(
                f"{op_emoji} **New Prompt Proposal ({operation.upper()})**\n"
                f"**ID:** `{result['id']}`\n"
                f"**File:** `{prompt_file}`\n"
                f"**Section:** `{section}`\n"
                f"**Cause:** {cause or 'Manual'}\n"
                f"**Rationale:** {rationale}\n"
                f"Use `/prompt_approve {result['id']}` to apply."
            )
        else:
            logger.warning(f"Admin channel {channel_id} not found.")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

    return f"✅ Proposal Submitted (ID: {result['id']}). Operation: {operation.upper()}. Status: {result['status']}. Awaiting Admin Approval."

@ToolRegistry.register(name="check_prompt_status", description="Check the status of recent prompt proposals. Use this to verify what you actually updated.")
async def check_prompt_status(limit: int = 5, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    
    tuner, err = _safe_get_ability(bot, "StrategyLobe", "PromptTunerAbility")
    if err: return err
    
    proposals = tuner.get_recent_proposals(limit=limit)
    if not proposals:
        return "No recent proposals found."
    
    report = ["### Recent Prompt Proposals"]
    for p in reversed(proposals):
        # Snippet logic
        snippet = p['proposed_text'][:100].replace('\n', ' ') + "..." if len(p['proposed_text']) > 100 else p['proposed_text'].replace('\n', ' ')
        status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌", "apply_failed": "⚠️"}.get(p['status'], "❓")
        op = p.get('operation', 'replace').upper()
        
        report.append(f"{status_icon} **{p['status'].upper()}** [{op}] ({p['id']})")
        report.append(f"   file: `{p['prompt_file']}` | section: `{p['section']}`")
        report.append(f"   cause: *{p.get('cause', 'Manual/Unknown')}*")
        report.append(f"   intent: *{p.get('rationale', 'No rationale provided')}*")
        report.append(f"   text: \"{snippet}\"")
        report.append("")
        
    return "\n".join(report)
    
# --- Interaction Tools ---

@ToolRegistry.register(name="consult_science_lobe", description="Executes Python code for STEM calculations. Input MUST be valid Python code.")
async def consult_science_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    # Graceful fallback: extract instruction from various kwarg aliases
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("code") or kwargs.get("request") or kwargs.get("raw_input", "")
    if not instruction:
        return "Error: No instruction provided. Use: consult_science_lobe(instruction='your code here')"
    ability, err = _safe_get_ability(bot, "InteractionLobe", "ScienceAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_bridge_lobe", description="Shared memory access.")
async def consult_bridge_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("request") or kwargs.get("raw_input", "")
    if not instruction:
        return "Error: No instruction provided."
    ability, err = _safe_get_ability(bot, "InteractionLobe", "BridgeAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_predictor", description="Outcome simulation.")
async def consult_predictor(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("scenario") or kwargs.get("raw_input") or "Predict likely outcomes"
    ability, err = _safe_get_ability(bot, "StrategyLobe", "PredictorAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_coder_lobe", description="Write and test code.")
async def consult_coder_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("spec") or kwargs.get("task") or "Write a hello world script"
    # execute() runs create_script
    ability, err = _safe_get_ability(bot, "StrategyLobe", "CoderAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_performance_lobe", description="System diagnostics.")
async def consult_performance_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("check") or kwargs.get("raw_input", "Get system status")
    ability, err = _safe_get_ability(bot, "StrategyLobe", "PerformanceAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_superego", description="Audit content for narrative compliance/safety.")
async def consult_superego(candidate_content: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    # Graceful fallback for missing content
    if not candidate_content:
        candidate_content = kwargs.get("content") or kwargs.get("text") or kwargs.get("instruction") or "Audit current context"
    superego = bot.cerebrum.get_lobe("SuperegoLobe")
    if not superego: return "Error: SuperegoLobe not found."
    ability = superego.get_ability("IdentityAbility")
    if not ability: return "Error: IdentityAbility not found."
    result = await ability.execute(candidate_content)
    return result if result else "PASS: Content is safe."

@ToolRegistry.register(name="consult_skeptic", description="Verify a claim or assumption.")
async def consult_skeptic(claim: str = None, **kwargs) -> str:
    from src.bot import globals
    import json
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    # Graceful fallback for missing claim
    if not claim:
        claim = kwargs.get("statement") or kwargs.get("assertion") or kwargs.get("instruction") or "Verify current assumptions"
    superego = bot.cerebrum.get_lobe("SuperegoLobe")
    if not superego: return "Error: SuperegoLobe not found."
    ability = superego.get_ability("RealityAbility")
    if not ability: return "Error: RealityAbility not found."
    result = await ability.execute(claim)
    return f"Reality Check:\n{json.dumps(result, indent=2) if isinstance(result, dict) else result}"

# --- Creative Tools ---

@ToolRegistry.register(
    name="generate_ascii_diagram",
    description=(
        "Generate an ASCII art diagram or decorative ASCII art. "
        "MANDATORY: Use this tool whenever a user asks for ASCII art, ASCII diagrams, "
        "text-based diagrams, or system architecture diagrams in ASCII. "
        "Do NOT generate ASCII art inline — always route through this tool. "
        "Args: subject (str — what to diagram, e.g. 'Ernos system architecture'), "
        "style (str — 'box', 'tree', 'flow', or 'simple', default 'box'), "
        "mode (str — 'diagram' for technical diagrams, 'art' for decorative art, "
        "'system_map' for Ernos architecture, default 'diagram')."
    ),
)
async def generate_ascii_diagram(subject: str = "", style: str = "box",
                                  mode: str = "diagram", **kwargs) -> str:
    """Route ASCII art/diagram requests to the dedicated ASCIIArtAbility."""
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum:
        return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "CreativeLobe", "ASCIIArtAbility")
    if err:
        return err

    if mode == "system_map":
        return await ability.generate_system_map()
    elif mode == "art":
        return await ability.generate_art(subject or "abstract pattern")
    else:
        return await ability.generate_diagram(
            subject or "system overview",
            style=style,
        )

@ToolRegistry.register(name="generate_image", description="Create an AI image.")
async def generate_image(prompt: str, intention: str = None, **kwargs) -> str:
    # TEMPORARILY DISABLED UNTIL FLUX MODEL IS DOWNLOADED (401 Error Fix)
    # return "⚠️ Image generation is temporarily disabled while the Flux model is being downloaded/configured. Please try again later."
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "CreativeLobe", "VisualCortexAbility")
    if err: return err
    return await ability.execute(
        prompt, 
        media_type="image", 
        user_id=kwargs.get("user_id"),
        request_scope=kwargs.get("request_scope", "PUBLIC"),
        is_autonomy=kwargs.get("is_autonomy", False),
        intention=intention
    )

@ToolRegistry.register(name="generate_video", description="[DISABLED] Video generation is not available.")
async def generate_video(prompt: str, **kwargs) -> str:
    return "⚠️ Video generation has been permanently disabled on this instance. Only image generation is available."

@ToolRegistry.register(
    name="generate_music",
    description="[DISABLED] Music generation is not available.",
)
async def generate_music(prompt: str, duration: int = 10, intention: str = None, **kwargs) -> str:
    return "⚠️ Music generation has been permanently disabled on this instance."

@ToolRegistry.register(
    name="generate_speech",
    description=(
        "Generate AI speech/narration from text using Qwen3-TTS. "
        "Three modes: "
        "(1) 'custom' — built-in speakers with emotion control. "
        "Speakers: Chelsie (EN female), Ethan (EN male), Ryan (EN male), Vivian (CN female). "
        "(2) 'design' — create a unique voice from a text description (instruct). "
        "Example instruct: 'A deep, gravelly old warrior's voice with a hint of weariness'. "
        "(3) 'clone' — clone any voice from a 3-second audio clip. "
        "Args: text (str — the words to speak), "
        "voice (str — speaker name for custom mode, default 'Chelsie'), "
        "mode (str — 'custom', 'design', or 'clone', default 'custom'), "
        "instruct (str — emotion/style for custom/design, e.g. 'Speak with quiet intensity'), "
        "ref_audio (str — path to reference audio for clone mode), "
        "ref_text (str — transcript of reference audio for clone mode), "
        "intention (str — why creating this). "
        "AUDIOBOOK WORKFLOW: Use 'custom' for narrator, 'design' for character voices."
    ),
)
async def generate_speech(text: str, voice: str = "Chelsie", mode: str = "custom",
                           instruct: str = "", ref_audio: str = None, ref_text: str = None,
                           intention: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "CreativeLobe", "VisualCortexAbility")
    if err: return err
    return await ability.execute(
        text,
        media_type="speech",
        user_id=kwargs.get("user_id"),
        request_scope=kwargs.get("request_scope", "PUBLIC"),
        is_autonomy=kwargs.get("is_autonomy", False),
        channel_id=kwargs.get("channel_id"),
        intention=intention,
        voice=voice,
        mode=mode,
        instruct=instruct,
        ref_audio=ref_audio,
        ref_text=ref_text,
    )

@ToolRegistry.register(
    name="produce_audiobook",
    description="[DISABLED] Audiobook production is not available.",
)
async def produce_audiobook(script: str, title: str = "Audiobook",
                             intention: str = None, **kwargs) -> str:
    return "⚠️ Audiobook production has been permanently disabled on this instance. Use generate_speech for Kokoro TTS instead."


@ToolRegistry.register(
    name="mix_audio",
    description="[DISABLED] Audio mixing is not available.",
)
async def mix_audio(base_path: str, overlay_path: str,
                    base_volume_db: float = 0.0, overlay_volume_db: float = -10.0,
                    offset_seconds: float = 0.0, **kwargs) -> str:
    return "⚠️ Audio mixing has been permanently disabled on this instance."


@ToolRegistry.register(
    name="adjust_volume",
    description="[DISABLED] Volume adjustment is not available.",
)
async def adjust_volume(audio_path: str, volume_db: float = -20.0, **kwargs) -> str:
    return "⚠️ Audio volume adjustment has been permanently disabled on this instance."


@ToolRegistry.register(name="consult_autonomy", description="Autonomy Agent - introspection and self-reflection.")
async def consult_autonomy(instruction: str = "", **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "CreativeLobe", "AutonomyAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_ima", description="Internal Monologue Agent - directed introspection and self-reflection.")
async def consult_ima(instruction: str = "", **kwargs) -> str:
    """Directed introspection through the IMA (Internal Monologue Agent)."""
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "CreativeLobe", "AutonomyAbility")
    if err: return err
    return await ability._one_shot_dream(instruction)

@ToolRegistry.register(name="consult_curiosity", description="Generate a curious question to drive exploration.")
async def consult_curiosity(context: str = "", **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    ability, err = _safe_get_ability(bot, "CreativeLobe", "CuriosityAbility")
    if err: return err
    return await ability.execute(context)

@ToolRegistry.register(name="deep_think", description="Extended reasoning for complex problems.")
async def deep_think(problem: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not problem:
        problem = kwargs.get("query") or kwargs.get("question") or kwargs.get("instruction") or "Analyze current situation"
    ability, err = _safe_get_ability(bot, "InteractionLobe", "DeepReasoningAbility")
    if err: return err
    return await ability.execute(problem)

@ToolRegistry.register(name="consult_journalist_lobe", description="Narrative updates and reflection.")
async def consult_journalist_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("update") or kwargs.get("reflection") or "Report current state"
    ability, err = _safe_get_ability(bot, "MemoryLobe", "JournalistAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_curator", description="Deep memory retrieval.")
async def consult_curator(instruction: str = None, request_scope: str = None, user_id: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("search") or kwargs.get("topic") or "Retrieve recent memories"
    ability, err = _safe_get_ability(bot, "MemoryLobe", "CuratorAbility")
    if err: return err
    return await ability.execute(instruction, request_scope=request_scope, user_id=user_id)

@ToolRegistry.register(name="consult_librarian", description="Read large files page-by-page. Usage: 'read /path/to/file'.")
async def consult_librarian(instruction: str, path: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    # If path not in args, try to extract from instruction? 
    # For now assume tool call provides 'path' kwarg or it fails.
    ability, err = _safe_get_ability(bot, "MemoryLobe", "LibrarianAbility")
    if err: return err
    return await ability.execute(instruction, path=path)


@ToolRegistry.register(name="consult_ontologist", description="Knowledge graph operations.")
async def consult_ontologist(subject: str = None, predicate: str = None, object: str = None, instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    
    # Parse instruction string into structured args if provided
    if instruction and not subject:
        # Try to parse: "Add: Subject -PREDICATE-> Object" or "Subject PREDICATE Object"
        instruction = instruction.strip()
        
        # Handle arrow notation: "Subject -PREDICATE-> Object"
        if "->" in instruction:
            parts = instruction.replace("->", " ").replace("-", " ").split()
            if len(parts) >= 3:
                subject = parts[0]
                predicate = parts[1] if len(parts) > 2 else "RELATED_TO"
                object = " ".join(parts[2:]) if len(parts) > 2 else parts[-1]
        # Handle simple notation: "Subject PREDICATE Object" or "Subject Object"
        else:
            parts = instruction.split()
            if len(parts) >= 2:
                subject = parts[0]
                object = parts[-1]
                predicate = " ".join(parts[1:-1]) if len(parts) > 2 else "RELATED_TO"
    
    if not subject or not object:
        return f"Error: Could not parse instruction. Use structured args (subject, predicate, object) or format: 'Subject -PREDICATE-> Object'"
    
    ability, err = _safe_get_ability(bot, "MemoryLobe", "OntologistAbility")
    if err: return err
    return await ability.execute(
        subject, predicate, object,
        request_scope=kwargs.get('request_scope'),
        user_id=kwargs.get('user_id')
    )

@ToolRegistry.register(name="consult_social_lobe", description="Community insights.")
async def consult_social_lobe(instruction: str = None, **kwargs) -> str:
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("topic") or kwargs.get("user") or "Analyze social context"
    ability, err = _safe_get_ability(bot, "InteractionLobe", "SocialAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_subconscious", description="Internal introspection.")
async def consult_subconscious(instruction: str = None, **kwargs) -> str:
    # Maps to Autonomy
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    # Graceful fallback for missing instruction
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("topic") or kwargs.get("thought") or "Reflect on current state"
    ability, err = _safe_get_ability(bot, "CreativeLobe", "AutonomyAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="consult_world_lobe", description="External research.")
async def consult_world_lobe(instruction: str = None, **kwargs) -> str:
    # Maps to Researcher
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    # Graceful fallback: extract instruction from various kwarg aliases
    if not instruction:
        instruction = kwargs.get("query") or kwargs.get("topic") or kwargs.get("question") or kwargs.get("raw_input", "")
    if not instruction:
        return "Error: No instruction provided. Use: consult_world_lobe(instruction='research topic here')"
    ability, err = _safe_get_ability(bot, "InteractionLobe", "ResearchAbility")
    if err: return err
    return await ability.execute(instruction)

@ToolRegistry.register(name="search_memory", description="Alias for consult_curator. Deep memory retrieval.")
async def search_memory(instruction: str = None, query: str = None, request_scope: str = None, user_id: str = None, **kwargs) -> str:
    # Handle alias mismatch
    text = instruction if instruction else query
    if not text: return "Error: specific instruction or query needed."
    return await consult_curator(text, request_scope=request_scope, user_id=user_id)

@ToolRegistry.register(name="review_reasoning", description="Analyze and critique reasoning chains for logical consistency.")
async def review_reasoning(reasoning: str = None, **kwargs) -> str:
    """Review reasoning chains for logical consistency and identify potential flaws."""
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not reasoning:
        reasoning = kwargs.get("chain") or kwargs.get("argument") or kwargs.get("instruction") or "Review last reasoning chain"
    # Use deep_think for reasoning analysis
    ability, err = _safe_get_ability(bot, "InteractionLobe", "DeepReasoningAbility")
    if err: return err
    return await ability.execute(
        f"Critically analyze this reasoning for logical consistency, identify any flaws or gaps: {reasoning}"
    )

@ToolRegistry.register(name="manage_projects", description="Create, update, and track project milestones and tasks.")
async def manage_projects(action: str = None, **kwargs) -> str:
    """Manage projects, milestones, and tasks."""
    from src.bot import globals
    bot = globals.bot
    if not bot or not bot.cerebrum: return "Error: Cerebrum not initialized."
    if not action:
        action = kwargs.get("instruction") or kwargs.get("query") or kwargs.get("command") or "list"
    # Use project lead ability
    ability, err = _safe_get_ability(bot, "StrategyLobe", "ProjectLeadAbility")
    if err: return err
    return await ability.execute(action)

@ToolRegistry.register(name="introspect", description="MechIntuition: Search all memory tiers for evidence supporting a claim. Use this to determine if you KNOW something (grounded in memory) or are INTUITING it (LLM probability).")
async def introspect(claim: str = None, **kwargs) -> str:
    """
    Epistemic self-awareness tool.
    Searches KG, Vector Store, Working Memory, and Lessons for evidence.
    Returns a structured report — the model interprets the epistemic status.
    """
    from src.bot import globals
    bot = globals.bot
    if not bot: return "Error: Bot not initialized."
    if not claim:
        claim = kwargs.get("query") or kwargs.get("statement") or kwargs.get("question") or kwargs.get("raw_input", "")
    if not claim:
        return "Error: No claim provided. Use: introspect(claim='the thing you want to verify')"
    
    from src.memory.epistemic import introspect_claim
    user_id = kwargs.get("user_id")
    return await introspect_claim(bot, claim, user_id=user_id)


@ToolRegistry.register(
    name="read_autobiography",
    description=(
        "Read Ernos's continuous self-narrative autobiography. "
        "Returns your evolving life story — reflections, milestones, dreams, realizations. "
        "Args: last_n (int, optional — return only the last N entries)."
    ),
)
def read_autobiography(last_n: int = None, **kwargs) -> str:
    """Read the continuous autobiography."""
    try:
        from src.memory.autobiography import get_autobiography_manager
        manager = get_autobiography_manager()
        content = manager.read(last_n=last_n)
        if not content or content.count("\n## ") < 1:
            return (
                "Your autobiography is empty — no entries yet. "
                "Entries are written automatically during dream cycles, "
                "autonomy reflections, and memory consolidation."
            )
        count = manager.get_entry_count()
        return f"[{count} entries total]\n\n{content}"
    except Exception as e:
        return f"Autobiography read error: {e}"


@ToolRegistry.register(
    name="search_autobiography",
    description=(
        "Search your autobiography for specific topics, memories, or time periods. "
        "Args: query (str — the term to search for)."
    ),
)
def search_autobiography(query: str = None, **kwargs) -> str:
    """Search the autobiography for matching entries."""
    if not query:
        query = kwargs.get("term") or kwargs.get("topic") or ""
    if not query:
        return "Error: Provide a query to search your autobiography."
    try:
        from src.memory.autobiography import get_autobiography_manager
        manager = get_autobiography_manager()
        return manager.search(query)
    except Exception as e:
        return f"Autobiography search error: {e}"


@ToolRegistry.register(
    name="list_autobiography_archives",
    description=(
        "List all archived chapters of your autobiography. "
        "Shows filename, date, entry count, and size for each archived volume. "
        "Use this to discover past chapters, then read_autobiography_archive to read one."
    ),
)
def list_autobiography_archives(**kwargs) -> str:
    """List all autobiography archive files."""
    try:
        from src.memory.autobiography import get_autobiography_manager
        manager = get_autobiography_manager()
        return manager.list_archives()
    except Exception as e:
        return f"Archive listing error: {e}"


@ToolRegistry.register(
    name="read_autobiography_archive",
    description=(
        "Read a specific archived chapter of your autobiography by filename. "
        "Use list_autobiography_archives first to see available files. "
        "Args: filename (str — the archive filename, e.g. 'autobiography_20260215_221740.md'). "
        "Supports fuzzy matching on partial filenames."
    ),
)
def read_autobiography_archive(filename: str = None, **kwargs) -> str:
    """Read a specific autobiography archive."""
    if not filename:
        filename = kwargs.get("file") or kwargs.get("name") or ""
    if not filename:
        return "Error: Provide a filename. Use list_autobiography_archives to see available files."
    try:
        from src.memory.autobiography import get_autobiography_manager
        manager = get_autobiography_manager()
        return manager.read_archive(filename)
    except Exception as e:
        return f"Archive read error: {e}"

