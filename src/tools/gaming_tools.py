"""
Gaming Tools - Discord commands for game control.

Registers tools for starting games, executing commands, etc.
ADMIN ONLY - Only the admin can start gaming sessions.
"""
import logging
from src.tools.registry import ToolRegistry
import config.settings as settings

logger = logging.getLogger("Tools.Gaming")


@ToolRegistry.register(
    name="start_game",
    description="[ADMIN ONLY] Start a gaming session. Supports: minecraft"
)
async def start_game(
    game: str,
    host: str = "localhost",
    port: int = 65535,
    **kwargs
) -> str:
    """Start a gaming session. Admin only."""
    bot = kwargs.get("bot")
    channel = kwargs.get("channel")
    user_id = kwargs.get("user_id")
    
    # Admin check (handle both string and int user_id)
    try:
        uid = int(user_id) if user_id else None
    except (ValueError, TypeError):
        uid = None
    
    if uid not in settings.ADMIN_IDS:
        logger.warning(f"Gaming denied: user_id={user_id} (type={type(user_id)}), ADMIN_IDS={settings.ADMIN_IDS}")
        return "🔒 Gaming is admin-only. Request denied."
    
    if not bot:
        return "Error: No bot context"
    
    # GUARD: Check if game is already running - prevent duplicate launches
    if hasattr(bot, "gaming_agent") and bot.gaming_agent.is_running:
        logger.warning(f"start_game denied: Game session already running for {game}")
        return f"🎮 Game session already running! Use `stop_game` first to restart, or use `game_status` to check current state."
    
    if not hasattr(bot, "gaming_agent"):
        from src.gaming import GamingAgent
        bot.gaming_agent = GamingAgent(bot)
    
    success = await bot.gaming_agent.start(game, channel, host, port)
    
    if success:
        return f"🎮 Started {game} session! I'm now in the game."
    else:
        return f"❌ Failed to start {game} - is the server running?"



@ToolRegistry.register(
    name="stop_game",
    description="Stop the current gaming session"
)
async def stop_game(**kwargs) -> str:
    """Stop the gaming session."""
    bot = kwargs.get("bot")
    
    if not bot or not hasattr(bot, "gaming_agent"):
        return "No active gaming session"
    
    await bot.gaming_agent.stop()
    return "Gaming session stopped"


@ToolRegistry.register(
    name="game_command",
    description="Execute a game command (goto, collect, attack, craft, chat)"
)
async def game_command(command: str, **kwargs) -> str:
    """Execute a game command."""
    bot = kwargs.get("bot")
    
    if not bot or not hasattr(bot, "gaming_agent"):
        return "No active gaming session"
    
    if not bot.gaming_agent.is_running:
        return "Not currently playing a game"
    
    # Parse command string
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    # Map to bridge commands
    if cmd == "goto":
        coords = args.split()
        if len(coords) >= 3:
            x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
            result = await bot.gaming_agent.execute("goto", x=x, y=y, z=z)
        else:
            return "Usage: goto x y z"
    elif cmd == "collect":
        parts = args.split()
        block_type = parts[0] if parts else "oak_log"
        count = int(parts[1]) if len(parts) > 1 else 1
        result = await bot.gaming_agent.execute("collect", block_type=block_type, count=count)
    elif cmd == "attack":
        result = await bot.gaming_agent.execute("attack", entity_type=args or "hostile")
    elif cmd == "craft":
        parts = args.split()
        item = parts[0] if parts else ""
        count = int(parts[1]) if len(parts) > 1 else 1
        result = await bot.gaming_agent.execute("craft", item=item, count=count)
    elif cmd == "chat":
        result = await bot.gaming_agent.execute("chat", message=args)
    elif cmd == "status":
        result = await bot.gaming_agent.execute("status")
    elif cmd == "follow":
        result = await bot.gaming_agent.execute("follow", username=args)
    else:
        return f"Unknown command: {cmd}"
    
    if result.get("success"):
        return f"✅ {cmd}: {result.get('data')}"
    else:
        return f"❌ {cmd} failed: {result.get('error')}"


@ToolRegistry.register(
    name="game_status",
    description="Get current game status (health, position, inventory)"
)
async def game_status(**kwargs) -> str:
    """Get game status."""
    bot = kwargs.get("bot")
    
    if not bot or not hasattr(bot, "gaming_agent"):
        return "Not playing"
    
    if not bot.gaming_agent.is_running:
        return "Not currently playing a game"
    
    result = await bot.gaming_agent.execute("status")
    
    if result.get("success"):
        data = result.get("data", {})
        pos = data.get("position", {})
        inv = data.get("inventory", [])
        
        return (
            f"Health: {data.get('health')}/20 | Food: {data.get('food')}/20\n"
            f"Position: ({pos.get('x')}, {pos.get('y')}, {pos.get('z')})\n"
            f"Inventory: {len(inv)} items"
        )
    else:
        return f"Error: {result.get('error')}"
