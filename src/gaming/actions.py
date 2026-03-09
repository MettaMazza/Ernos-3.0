"""
Gaming Actions — Action dispatch for Minecraft game commands.

Extracted from gaming/agent.py per <300 line modularity standard.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from .planner import HierarchicalPlanner, plan_goal
from .skill_library import get_skill_library

logger = logging.getLogger("Gaming.Actions")

# Import mc_log from agent module
from .agent import mc_log, log_embodiment


class ActionsMixin:
    """
    Mixin providing the _act method for GamingAgent.
    
    Requires: self.bridge, self._current_goal, self._goal_start_time,
              self._goal_actions, self._action_queue, self._following_player,
              self._pending_chats
    """

    async def _act(self, action: str):
        """Execute the decided action."""
        logger.info(f"Executing action: {action}")
        
        parts = action.strip().split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        try:
            # === HIERARCHICAL PLANNING ===
            if cmd in ("plan", "get", "obtain", "make") and args:
                await self._act_hierarchical(cmd, args)
                return
            
            # Execute queued actions if any
            if cmd == "continue" and self._action_queue:
                next_action = self._action_queue.pop(0)
                remaining = len(self._action_queue)
                mc_log("DEBUG", "CONTINUE_PLAN", action=next_action, remaining=remaining)
                await self._act(next_action)
                return
            
            # === Core Actions ===
            if cmd == "goto" and len(args) >= 3:
                x, y, z = float(args[0]), float(args[1]), float(args[2])
                await self.bridge.goto(x, y, z)
            elif cmd == "collect" and args:
                block_type = args[0]
                count = int(args[1]) if len(args) > 1 else 1
                await self.bridge.collect(block_type, count)
            elif cmd == "craft" and args:
                item = args[0]
                count = int(args[1]) if len(args) > 1 else 1
                await self.bridge.craft(item, count)
            elif cmd == "attack":
                target = args[0] if args else "hostile"
                result = await self.bridge.attack(target)
                return result.success if result else False
            elif cmd == "chat" and args:
                message = " ".join(args)
                await self.bridge.chat(message)
                log_embodiment("chat_sent", f"I said in chat: '{message}'")
            elif cmd == "follow" and args:
                await self._act_follow(args[0])
            elif cmd == "explore":
                await self._act_explore()
            elif cmd == "protect":
                await self._act_protect(args)
            
            # === Combat & Survival ===
            elif cmd == "equip" and args:
                item = args[0]
                slot = args[1] if len(args) > 1 else "hand"
                result = await self.bridge.equip(item, slot)
                if result.success:
                    log_embodiment("item_equipped", f"I equipped {item} to {slot}")
            elif cmd == "shield":
                activate = args[0].lower() != "down" if args else True
                result = await self.bridge.shield(activate)
                if result.success:
                    log_embodiment("shield_action", f"I {'raised' if activate else 'lowered'} my shield")
            elif cmd == "sleep":
                result = await self.bridge.sleep()
                if result.success:
                    log_embodiment("sleeping", "I went to sleep in a bed")
            elif cmd == "wake":
                result = await self.bridge.wake()
                if result.success:
                    log_embodiment("woke_up", "I woke up from the bed")
            
            # === Resource Management ===
            elif cmd == "smelt" and args:
                input_item = args[0]
                fuel = args[1] if len(args) > 1 else "coal"
                count = int(args[2]) if len(args) > 2 else 1
                result = await self.bridge.smelt(input_item, fuel, count)
                if result.success:
                    log_embodiment("smelted", f"I smelted {count} {input_item}")
            elif cmd == "store":
                item = args[0] if args else None
                count = int(args[1]) if len(args) > 1 else None
                result = await self.bridge.store(item, count)
                if result.success:
                    log_embodiment("stored_items", "I stored items in chest")
            elif cmd == "take":
                item = args[0] if args else None
                count = int(args[1]) if len(args) > 1 else None
                result = await self.bridge.take(item, count)
                if result.success:
                    log_embodiment("took_items", "I took items from chest")
            elif cmd == "place" and args:
                block = args[0]
                x = int(args[1]) if len(args) > 1 else None
                y = int(args[2]) if len(args) > 2 else None
                z = int(args[3]) if len(args) > 3 else None
                result = await self.bridge.place(block, x, y, z)
                if result.success:
                    log_embodiment("placed_block", f"I placed {block}")
            
            # === Farming & Sustainability ===
            elif cmd == "farm":
                crop = args[0] if args else "wheat"
                radius = int(args[1]) if len(args) > 1 else 3
                result = await self.bridge.farm(crop, radius)
                if result.success:
                    log_embodiment("farmed", f"I tilled and planted {crop}")
            elif cmd == "harvest":
                radius = int(args[0]) if args else 5
                result = await self.bridge.harvest(radius)
                if result.success:
                    log_embodiment("harvested", "I harvested crops")
            elif cmd == "plant":
                seed = args[0] if args else "wheat_seeds"
                count = int(args[1]) if len(args) > 1 else 1
                result = await self.bridge.plant(seed, count)
                if result.success:
                    log_embodiment("planted", f"I planted {seed}")
            elif cmd == "fish":
                duration = int(args[0]) if args else 30
                result = await self.bridge.fish(duration)
                if result.success:
                    log_embodiment("fished", "I went fishing")
            
            # === Location & Building ===
            elif cmd == "save_location" and args:
                name = args[0]
                result = await self.bridge.save_location(name)
                if result.success:
                    log_embodiment("location_saved", f"I saved this location as '{name}'")
            elif cmd == "goto_location":
                name = args[0] if args else None
                result = await self.bridge.goto_location(name)
                if result.success and name:
                    log_embodiment("arrived", f"I arrived at '{name}'")
            elif cmd == "copy_build" and args:
                name = args[0]
                radius = int(args[1]) if len(args) > 1 else 5
                height = int(args[2]) if len(args) > 2 else 10
                result = await self.bridge.copy_build(name, radius, height)
                if result.success:
                    log_embodiment("blueprint_saved", f"I copied this build as '{name}'")
            elif cmd == "build":
                if args:
                    name = args[0]
                    result = await self.bridge.build(name)
                    if result.success:
                        log_embodiment("built", f"I built '{name}'")
                else:
                    mc_log("WARNING", "BUILD_NO_NAME", msg="No blueprint name specified")
                    result = await self.bridge.list_blueprints()
            
            # === Co-op Mode ===
            elif cmd == "drop" and args:
                item = args[0]
                count = int(args[1]) if len(args) > 1 else 1
                result = await self.bridge.drop(item, count)
                if result.success:
                    log_embodiment("dropped", f"I dropped {count} {item}")
            elif cmd == "give" and len(args) >= 2:
                player = args[0]
                item = args[1]
                count = int(args[2]) if len(args) > 2 else 1
                result = await self.bridge.give(player, item, count)
                if result.success:
                    log_embodiment("gave", f"I gave {item} to {player}", mc_username=player)
            elif cmd == "find" and args:
                block = args[0]
                go = len(args) > 1 and args[1].lower() in ['go', 'true', 'yes']
                result = await self.bridge.find(block, go)
                if result.success:
                    log_embodiment("found", f"I found {block}")
            elif cmd == "eat":
                await self._act_eat(args)
            elif cmd == "share" and args:
                item = args[0]
                result = await self.bridge.share(item)
                if result.success:
                    log_embodiment("shared", f"I shared {item} with my teammate")
            elif cmd == "scan":
                radius = int(args[0]) if args else 32
                result = await self.bridge.scan(radius)
                if result.success:
                    log_embodiment("scanned", "I scanned for nearby resources")
            elif cmd in ("coop", "coop_mode"):
                if args:
                    player = args[0]
                    mode = args[1] if len(args) > 1 else "on"
                    result = await self.bridge.coop_mode(player, mode)
                    if result.success:
                        log_embodiment("coop_mode", f"I'm now in co-op mode with {player}")
        except Exception as e:
            logger.error(f"Action error: {e}")
            # === SELF-DEBUGGING: Reflect on failure ===
            retry_action = self._reflect_on_failure(action, str(e))
            if retry_action and retry_action != action:
                mc_log("INFO", "SELF_DEBUG_RETRY", original=action, retry=retry_action)
                log_embodiment("debugging", f"The action '{action}' failed. I'll try '{retry_action}' instead.")
                await self._act(retry_action)

    # === Private helpers for complex actions ===

    async def _act_hierarchical(self, cmd: str, args: list):
        """Handle hierarchical planning actions (get/plan/obtain/make)."""
        goal = args[0]
        count = int(args[1]) if len(args) > 1 else 1
        
        # Check skill library first
        skill_lib = get_skill_library()
        existing_skill = skill_lib.retrieve(goal)
        
        if existing_skill and existing_skill.success_rate >= 0.5:
            mc_log("INFO", "SKILL_REUSE", skill=existing_skill.name, success_rate=existing_skill.success_rate)
            log_embodiment("skill_reuse", f"I know how to get {goal}! Using my learned skill.")
            actions = existing_skill.steps
        else:
            status = await self.bridge.get_status()
            inventory = {}
            if status.success and "inventory" in status.data:
                for item in status.data["inventory"]:
                    inventory[item["name"]] = item.get("count", 1)
            
            actions = plan_goal(goal, inventory)
        
        if actions:
            mc_log("INFO", "HIERARCHICAL_PLAN", goal=goal, steps=len(actions))
            log_embodiment("planning", f"I'm planning how to get {goal}: {len(actions)} steps")
            
            self._current_goal = goal
            self._goal_start_time = datetime.now()
            self._goal_actions = actions.copy()
            self._action_queue = actions
            
            if self._action_queue:
                first_action = self._action_queue.pop(0)
                await self._act(first_action)
        else:
            await self.bridge.chat(f"I already have {goal}!")

    async def _act_follow(self, player_name: str):
        """Handle follow action."""
        if self._following_player == player_name:
            mc_log("DEBUG", "ALREADY_FOLLOWING", player=player_name)
            return
        await self.bridge.follow(player_name)
        self._following_player = player_name
        log_embodiment("follow_start", f"I started following {player_name}", mc_username=player_name)

    async def _act_explore(self):
        """Handle explore action — random wander."""
        import random
        pos = await self.bridge.get_status()
        if pos.success:
            x = pos.data["position"]["x"] + random.randint(-20, 20)
            z = pos.data["position"]["z"] + random.randint(-20, 20)
            await self.bridge.goto(x, 64, z)

    async def _act_protect(self, args: list):
        """Handle protect action."""
        radius = int(args[0]) if args else 50
        requester = "unknown"
        if self._pending_chats:
            requester = self._pending_chats[-1].get("username", "unknown")
        result = await self.bridge.protect(username=requester, radius=radius)
        if result.success:
            log_embodiment("protect_zone_created", f"I created a {radius}-block protected zone for {requester}", mc_username=requester)

    async def _act_eat(self, args: list):
        """Handle eat action with auto-find food in inventory."""
        food = args[0] if args else None
        if not food:
            status = await self.bridge.get_status()
            if status.success:
                inv = status.data.get("inventory", [])
                edibles = ["cooked_beef", "cooked_porkchop", "cooked_chicken", "bread", "apple", "golden_apple", "cooked_mutton", "cooked_rabbit", "cooked_cod", "cooked_salmon", "baked_potato", "pumpkin_pie", "cake", "cookie", "melon_slice", "beef", "porkchop", "chicken", "mutton", "rabbit", "cod", "salmon", "potato", "carrot", "beetroot"]
                for item in inv:
                    if item.get("name") in edibles:
                        food = item.get("name")
                        break
        if food:
            result = await self.bridge.eat(food)
            if result.success:
                log_embodiment("ate", f"I ate {food}")
        else:
            mc_log("WARNING", "EAT_NO_FOOD", msg="No food found in inventory")
