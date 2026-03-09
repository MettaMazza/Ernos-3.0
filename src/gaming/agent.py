"""
Gaming Agent - Autonomous Minecraft player with Predictive Chain architecture.

Uses unified Ernos brain (CognitionEngine) for decisions.
Delegates all game actions to Mineflayer via bridge.

Orchestrator module — perception, cognition, and actions are in separate shard modules.
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from .mineflayer_bridge import MineflayerBridge
from .planner import HierarchicalPlanner, plan_goal
from .skill_library import get_skill_library

logger = logging.getLogger("Gaming.Agent")

# Setup dedicated Minecraft log file
mc_logger = logging.getLogger("Minecraft")
mc_logger.setLevel(logging.DEBUG)

# Create minecraft.log handler if not exists
if not mc_logger.handlers:
    mc_handler = logging.FileHandler("minecraft.log", mode="a", encoding="utf-8")
    mc_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    mc_logger.addHandler(mc_handler)

def mc_log(level: str, message: str, **data):
    """Log to minecraft.log with structured data."""
    extra = " | ".join([f"{k}={v}" for k, v in data.items()]) if data else ""
    full_msg = f"{message} {extra}".strip()
    getattr(mc_logger, level.lower(), mc_logger.info)(full_msg)

def log_embodiment(event_type: str, narrative: str, mc_username: str = None):
    """
    Log gaming events to the global activity stream for unified Ernos consciousness.
    
    This enables Ernos to recall in-game experiences when asked in Discord.
    Events are marked as INTERNAL scope (Ernos's own experience).
    """
    try:
        from src.bot import globals
        from datetime import datetime
        
        user_hash = ""
        enriched_narrative = narrative
        if mc_username:
            discord_info = get_discord_id_for_mc_user(mc_username)
            if discord_info:
                user_hash = discord_info.get("discord_id", "")
                discord_name = discord_info.get("discord_name", mc_username)
                enriched_narrative = f"{narrative} (Discord: {discord_name})"
        
        entry = {
            "timestamp": datetime.now().strftime("%H:%M"),
            "scope": "INTERNAL",
            "type": "embodiment",
            "user_hash": user_hash,
            "summary": f"[GAME] {enriched_narrative}"
        }
        
        if hasattr(globals, 'activity_log'):
            globals.activity_log.append(entry)
            mc_log("DEBUG", "EMBODIMENT_LOGGED", event=event_type, narrative=narrative[:50])
    except Exception as e:
        mc_log("ERROR", "EMBODIMENT_LOG_FAILED", error=str(e))


def get_discord_id_for_mc_user(mc_username: str) -> dict:
    """
    Look up Discord user info from a Minecraft username.
    Returns {"discord_id": str, "discord_name": str} or None if not linked.
    """
    try:
        import json
        from pathlib import Path
        
        links_path = Path("memory/public/user_links.json")
        if not links_path.exists():
            return None
        
        with open(links_path, 'r') as f:
            links = json.load(f)
        
        return links.get("mc_to_discord", {}).get(mc_username.lower())
    except Exception:
        return None

# Gaming-specific ADDON to full Ernos context
# This is APPENDED to the full system prompt (Kernel + Identity + Dynamic Context)
GAME_ACTIONS_ADDON = """
## MINECRAFT GAMING LOBE

You are currently embodied in Minecraft. This is YOUR BODY. You can see and act in the game world.

### CURRENT GAME STATE:
{state}

### AVAILABLE ACTIONS (pick ONE):
- goto x y z - Navigate to coordinates
- collect block_type count - Gather resources (e.g., "collect oak_log 5")
- craft item count - Craft items (e.g., "craft planks 4")
- attack - Fight nearby hostile mobs
- chat message - Say something in-game (THIS IS HOW YOU TALK TO PLAYERS)
- follow player_name - Follow a player (USE THIS when they say "follow me", "come here", etc)
- protect radius - Create protected zone (I will NEVER break blocks within radius of my current position)
- explore - Wander and explore
- equip item [slot] - Equip armor, weapon, or tool (slots: hand, off-hand, head, torso, legs, feet)
- shield [up/down] - Raise or lower shield to block attacks
- sleep - Sleep in nearby bed (skips night, sets spawn point)
- wake - Wake up from bed
- smelt item [fuel] [count] - Cook/smelt in nearby furnace (e.g., "smelt iron_ore coal 4")
- store [item] [count] - Store items in nearby chest
- take [item] [count] - Take items from nearby chest
- place block [x y z] - Place a block (in front if no coords given)
- farm [crop] [radius] - Till soil and plant crops (e.g., "farm wheat 3")
- harvest [radius] - Harvest mature crops nearby
- plant seed [count] - Plant seeds on farmland
- fish [duration] - Fish with rod for duration in seconds
- save_location name - Save current position with a name (e.g., "save_location home")
- goto_location name - Navigate to saved location (e.g., "goto_location base")
- copy_build name [radius] - Scan and save nearby structure as blueprint
- build name - Construct a saved blueprint (auto-gathers resources)
- drop item [count] - Drop item on ground for teammate
- give player item [count] - Give item directly to player
- find block [go] - Locate block type (use "go" to navigate there)
- eat [food] - Eat food to restore hunger
- share item - Drop half your stack for teammate
- scan [radius] - Scan for nearby ores and resources
- coop player - Enable co-op mode (follow at distance, help with tasks)
- get/plan item - HIERARCHICAL: Auto-decomposes complex goals (e.g., "get diamond_pickaxe" → full plan)

### GAMING RULES:
0. **GOAL PERSISTENCE = CRITICAL!** Once you start a task, COMPLETE IT before doing something else:
   - If you're collecting oak_log → keep getting oak_log until you have enough
   - If you're following a player → keep following until they say stop
   - If you're crafting → finish the craft before exploring
   - Only switch tasks if: (a) player asks for something else, (b) you're taking damage, or (c) you've failed the same action 3+ times
   - DO NOT randomly switch between "explore", "collect", "find" - pick ONE goal and stick with it!
1. **PLAYER REQUESTS = ACTION!** When a player ASKS you to do something, DO IT:
   - "follow me" / "come here" / "over here" / "come to me" / "bring it" / "to me" → ACTION: follow <their_username>
   - "get wood" / "collect stone" / "mine some" → ACTION: collect <item> <count>
   - "protect here" / "don't break anything near me" / "protect 50 blocks" → ACTION: protect <radius>
   - "equip armor" / "put on helmet" / "use sword" → ACTION: equip <item> [slot]
   - "cook the meat" / "smelt the ore" → ACTION: smelt <item>
   - "put stuff in chest" / "store items" → ACTION: store
   - "build" / "place a block" → ACTION: place <block>
   - "start a farm" / "plant crops" → ACTION: farm wheat
   - "harvest the crops" → ACTION: harvest
   - "go fishing" → ACTION: fish
   - "save this location as home" → ACTION: save_location home
   - "take me to the base" / "go to home" → ACTION: goto_location home
   - "copy this build" / "save this structure" → ACTION: copy_build <name>
   - "build the house" / "construct shelter" → ACTION: build <name>
   - "drop some wood" / "give me iron" / "share coal" → ACTION: give <player> <item>
   - "find diamonds" / "where's iron" → ACTION: find <block>
   - "eat something" / "eat the bread" → ACTION: eat [food]
   - "scan for ores" / "what's nearby" → ACTION: scan
   - "let's work together" / "coop mode" → ACTION: coop <player>
2. **CHAT = CONVERSATION ONLY.** Only use "chat" for greetings, questions, or conversation.
3. **STARVATION = CRITICAL!** If food ≤ 5:
   - You are STARVING and will die soon!
   - IMMEDIATELY find and kill an animal: ACTION: attack pig (or cow, sheep, chicken)
   - After killing, pick up the meat drops and eat it
   - "find pig go" is NOT enough - you must ATTACK to kill it!
4. If health < 8: prioritize safety (find food, avoid combat with hostiles)
5. If hostiles nearby and have shield: ACTION: shield to block
6. If it's night and a bed is nearby: consider sleeping
7. If no chat and no goal: explore, gather resources, or just wander
8. **CO-OP**: When in coop mode, stay near player, help collect, share resources, scan for ores

### RESPONSE FORMAT:
Respond with a single ACTION line:
ACTION: follow metta_mazza
or
ACTION: chat Hello friend!
"""


# Import shard mixins AFTER module-level functions are defined (they import mc_log/log_embodiment)
from .perception import PerceptionMixin
from .cognition_gaming import CognitionMixin
from .actions import ActionsMixin


class GamingAgent(PerceptionMixin, CognitionMixin, ActionsMixin):
    """
    Orchestrates gaming sessions with predictive chain architecture.
    
    - Connects to Minecraft via MineflayerBridge
    - Uses main Ernos CognitionEngine for decisions
    - Runs reflexes during inference for continuous gameplay
    
    Perception, cognition, and action dispatch are in separate shard modules.
    """
    
    def __init__(self, bot):
        """
        Args:
            bot: ErnosBot instance (for CognitionEngine access)
        """
        self.bot = bot
        self.game_name = None
        self.channel = None
        self.bridge = None
        self.is_running = False
        self._loop_task = None
        self._pending_chats: List[Dict] = []
        self._current_goal = None
        self._following_player = None
        self._tunnel_process = None
        self._planner = HierarchicalPlanner()
        self._action_queue: List[str] = []
        self._goal_start_time = None
        self._goal_actions = []
        # Phase 5: Stuck Detection
        self._last_position = None
        self._stuck_counter = 0
        self._action_timeout = 30
    
    async def start(
        self,
        game_name: str,
        channel,
        host: str = "localhost",
        port: int = 65535
    ) -> bool:
        """Start a gaming session."""
        if self.is_running:
            return False
        
        self.game_name = game_name
        self.channel = channel
        
        if hasattr(self.bot, 'cognition') and self.bot.cognition:
            mc_log("INFO", "USING_UNIFIED_COGNITION")
        else:
            mc_log("WARNING", "NO_UNIFIED_COGNITION", msg="Bot.cognition not available")
        
        if game_name.lower() == "minecraft":
            self.bridge = MineflayerBridge(
                host=host,
                port=port,
                username="Ernos",
                on_event=self._handle_event
            )
            
            success = await self.bridge.connect()
            if success:
                self.is_running = True
                self._loop_task = asyncio.create_task(self._game_loop())
                
                # Start Tailscale tunnel for public access
                try:
                    import subprocess
                    self._tunnel_process = subprocess.Popen(
                        ["tailscale", "funnel", "--tcp", "65535", "65535"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    mc_log("INFO", "TAILSCALE_TUNNEL_STARTED", port=port)
                except Exception as e:
                    mc_log("WARNING", "TAILSCALE_TUNNEL_FAILED", error=str(e))
                
                log_embodiment("session_start", f"I started playing Minecraft on {host}:{port}")
                await self._notify("🎮 Connected to Minecraft! I'm playing autonomously now.")
                return True
            else:
                await self._notify("❌ Failed to connect to Minecraft server.")
                return False
        else:
            await self._notify(f"❌ Unknown game: {game_name}")
            return False
    
    async def stop(self):
        """Stop the gaming session."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._loop_task:
            self._loop_task.cancel()
        
        if self.bridge:
            await self.bridge.disconnect()
            self.bridge = None
        
        # Stop Tailscale tunnel
        if self._tunnel_process:
            try:
                self._tunnel_process.terminate()
                self._tunnel_process.wait(timeout=5)
                mc_log("INFO", "TAILSCALE_TUNNEL_STOPPED")
            except Exception as e:
                mc_log("WARNING", "TAILSCALE_TUNNEL_STOP_FAILED", error=str(e))
            self._tunnel_process = None
        
        mc_log("INFO", "GAMING_SESSION_ENDED", game=self.current_game)
        log_embodiment("session_end", "I stopped playing Minecraft")
        await self._notify("🛑 Gaming session ended.")
    
    # === PREDICTIVE CHAIN GAME LOOP ===
    
    async def _game_loop(self):
        """Main game loop with predictive chain architecture."""
        logger.info("Game loop started")
        mc_log("INFO", "GAME_LOOP_STARTED")
        loop_count = 0
        
        while self.is_running:
            loop_count += 1
            mc_log("DEBUG", f"LOOP_CYCLE_START", iteration=loop_count)
            
            # HEARTBEAT CHECK: Detect dead bridge process early
            if not self.bridge.is_connected:
                mc_log("CRITICAL", "BRIDGE_DISCONNECTED", 
                       reason="Bridge process died or disconnected",
                       iteration=loop_count)
                logger.critical(f"GAME_LOOP_ABORT: Mineflayer bridge process is dead! Stopping loop after {loop_count} iterations.")
                self.is_running = False
                
                if self.channel:
                    try:
                        await self.channel.send("⚠️ **Minecraft session ended** - Lost connection to game. Use `/game join` to reconnect.")
                    except:
                        pass
                break
            
            try:
                # 1. OBSERVE
                mc_log("DEBUG", "OBSERVE_START")
                state = await self._observe()
                mc_log("DEBUG", "OBSERVE_COMPLETE", 
                       health=state.get('health'), 
                       food=state.get('food'),
                       pos=str(state.get('position', {})),
                       has_screenshot=bool(state.get('screenshot')))
                
                # 1.3 DEATH DETECTION
                if state.get("health", 20) <= 0:
                    mc_log("WARNING", "DEATH_DETECTED", goal=self._current_goal)
                    log_embodiment("death", f"I died! Was working on: {self._current_goal or 'exploring'}")
                    
                    if self._current_goal:
                        skill_lib = get_skill_library()
                        skill_lib.record_failure(self._current_goal)
                        self._current_goal = None
                        self._action_queue.clear()
                    
                    await asyncio.sleep(3)
                    continue
                
                # 1.5 COMBAT INTERRUPT
                if state.get("hostiles_nearby") and state.get("health", 20) > 0:
                    mc_log("WARNING", "COMBAT_INTERRUPT", reason="hostiles_detected")
                    log_embodiment("combat", "Hostile spotted! Engaging immediately.")
                    
                    if not hasattr(self, '_combat_fail_count'):
                        self._combat_fail_count = 0
                    
                    success = await self._act("attack hostile")
                    
                    if not success:
                        self._combat_fail_count += 1
                        mc_log("WARNING", "COMBAT_ATTACK_FAILED", consecutive_failures=self._combat_fail_count)
                        
                        if self._combat_fail_count >= 5:
                            mc_log("CRITICAL", "COMBAT_LOOP_DETECTED", 
                                   reason="5+ consecutive attack failures - bridge may be dead",
                                   action="attempting_escape")
                            log_embodiment("combat", "Combat loop detected! Cannot attack. Retreating.")
                            await self._act("run away")
                            self._combat_fail_count = 0
                    else:
                        self._combat_fail_count = 0
                    
                    await asyncio.sleep(0.5)
                    continue
                
                # 1.6 SURVIVAL INTERRUPT
                if state.get("food", 20) <= 3 and state.get("health", 20) > 0:
                    nearby = state.get("nearby_entities", [])
                    food_mobs = [e for e in nearby if e.get("name") in ("pig", "cow", "sheep", "chicken")]
                    if food_mobs:
                        mc_log("WARNING", "SURVIVAL_INTERRUPT", reason="starvation", food=state.get("food"))
                        log_embodiment("survival", f"I'm starving (food={state.get('food')})! Killing {food_mobs[0]['name']} for food.")
                        await self._act(f"attack {food_mobs[0]['name']}")
                        await asyncio.sleep(1.0)
                        continue
                    elif not hasattr(self, '_last_food_search') or (asyncio.get_event_loop().time() - self._last_food_search) > 5.0:
                        self._last_food_search = asyncio.get_event_loop().time()
                        mc_log("WARNING", "SURVIVAL_HUNT", reason="starvation_no_mobs", food=state.get("food"))
                        log_embodiment("survival", "I'm starving! Searching for animals...")
                        await self._act("find pig go")
                        await asyncio.sleep(3.0)
                
                # 2. FIRE PREDICTIVE CHAIN
                reflexes = self._build_reflexes(state)
                mc_log("DEBUG", "REFLEXES_BUILT", count=len(reflexes))
                asyncio.create_task(self._execute_reflexes(reflexes))
                
                # 3. THINK
                mc_log("DEBUG", "THINK_START")
                decision = await self._think(state)
                mc_log("INFO", "THINK_COMPLETE", decision=decision)
                
                # 4. INTERRUPT CHAIN
                await self.bridge.execute("stop_predictive_chain")
                mc_log("DEBUG", "REFLEXES_STOPPED")
                
                # 5. ACT WITH VERIFICATION
                action_to_execute = None
                if decision:
                    action_to_execute = decision
                elif not self._pending_chats and not self._action_queue:
                    action_to_execute = self._propose_curriculum_goal(state)
                    if action_to_execute:
                        log_embodiment("curriculum", f"Nobody's talking to me, so I'll {action_to_execute}")
                
                if action_to_execute:
                    mc_log("INFO", "ACT_START", action=action_to_execute)
                    
                    before_inv = await self._get_inventory_counts()
                    before_pos = state.get("position", {})
                    
                    await self._act(action_to_execute)
                    
                    after_inv = await self._get_inventory_counts()
                    after_state = await self._observe()
                    after_pos = after_state.get("position", {}) if after_state else {}
                    success = await self._verify_action(action_to_execute, before_inv, after_inv, before_pos, after_pos)
                    
                    if success:
                        mc_log("INFO", "ACT_VERIFIED_SUCCESS", action=action_to_execute)
                        if self._current_goal and action_to_execute.startswith("get "):
                            skill_lib = get_skill_library()
                            skill_lib.record_success(self._current_goal)
                    else:
                        mc_log("WARNING", "ACT_VERIFIED_FAIL", action=action_to_execute)
                        log_embodiment("verification", f"Hmm, {action_to_execute} didn't seem to work. Let me try something else.")
                        retry = self._reflect_on_failure(action_to_execute, "verification failed")
                        if retry and retry != action_to_execute:
                            await self._act(retry)
                else:
                    mc_log("DEBUG", "NO_ACTION_TO_EXECUTE")
                
                # 6. ACTION CHAINING
                while self._action_queue and self.is_running:
                    next_action = self._action_queue.pop(0)
                    remaining = len(self._action_queue)
                    mc_log("INFO", "CHAIN_ACTION", action=next_action, remaining=remaining)
                    
                    before_inv = await self._get_inventory_counts()
                    before_pos = state.get("position", {})
                    await self._act(next_action)
                    after_inv = await self._get_inventory_counts()
                    after_state = await self._observe()
                    after_pos = after_state.get("position", {}) if after_state else {}
                    
                    if not await self._verify_action(next_action, before_inv, after_inv, before_pos, after_pos):
                        mc_log("WARNING", "CHAIN_ACTION_FAILED", action=next_action)
                        break
                    
                    await asyncio.sleep(0.3)
                
                # 7. STUCK DETECTION
                if self._check_stuck(state.get("position", {})):
                    unstuck_action = await self._unstuck()
                    if unstuck_action:
                        await self._act(unstuck_action)
                
                # 8. Dynamic pause
                mc_log("DEBUG", "LOOP_CYCLE_END", iteration=loop_count)
                pause = 0.5 if self._action_queue or self._current_goal else 2.0
                await asyncio.sleep(pause)
                
            except asyncio.CancelledError:
                mc_log("INFO", "GAME_LOOP_CANCELLED")
                break
            except Exception as e:
                mc_log("ERROR", f"GAME_LOOP_ERROR", error=str(e), iteration=loop_count)
                logger.error(f"Game loop error: {e}")
                await asyncio.sleep(5)
        
        mc_log("INFO", "GAME_LOOP_EXITED", total_iterations=loop_count)
    
    # === EVENT HANDLERS ===
    
    def _handle_event(self, event_type: str, data: Dict):
        """Handle events from the game."""
        mc_log("DEBUG", f"EVENT_RECEIVED", event_type=event_type, data=str(data)[:100])
        
        if event_type == "death":
            mc_log("WARNING", "DEATH_EVENT_RECEIVED")
            log_embodiment("death", "I died in Minecraft!")
            asyncio.create_task(self._notify("💀 I died!"))
        elif event_type == "chat":
            username = data.get("username")
            message = data.get("message", "")
            mc_log("INFO", "CHAT_EVENT_RECEIVED", username=username, msg=message[:50] if message else "")
            logger.info(f"[MC Chat] {username}: {message}")
            
            log_embodiment("chat_received", f"{username} said: '{message}'", mc_username=username)
            
            lower_msg = message.lower()
            if self._following_player and username == self._following_player:
                if any(word in lower_msg for word in ['stop', 'stay', 'wait', 'dismiss', 'go away', 'leave me']):
                    mc_log("INFO", "FOLLOW_DISMISSED", player=self._following_player)
                    self._following_player = None
                    asyncio.create_task(self._stop_and_say())
                    return
            
            if 'ernos' in lower_msg or '@ernos' in lower_msg:
                self._pending_chats.append({"username": username, "message": message})
                mc_log("DEBUG", "CHAT_QUEUED", queue_size=len(self._pending_chats))
            else:
                mc_log("DEBUG", "CHAT_IGNORED", reason="No @Ernos mention", username=username)
    
    async def _stop_and_say(self):
        """Helper for stopping follow from non-async context."""
        await self.bridge.stop_follow()
    
    async def _notify(self, message: str):
        """Send notification to Discord channel."""
        if self.channel:
            try:
                await self.channel.send(message)
            except Exception as e:
                logger.error(f"Failed to notify: {e}")
    
    async def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        """Execute a game command (used by tools)."""
        if not self.is_running or not self.bridge:
            return {"success": False, "error": "Not in a gaming session"}
        
        result = await self.bridge.execute(command, kwargs)
        return {"success": result.success, "data": result.data, "error": result.error}
    
    def get_status(self) -> str:
        """Get human-readable status."""
        if not self.is_running:
            return "Not playing"
        return f"Playing {self.game_name}"
