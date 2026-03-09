"""
Gaming Perception — Observation, reflexes, stuck detection, and action verification.

Extracted from gaming/agent.py per <300 line modularity standard.
All methods are designed as mixins and use the agent's bridge/state.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger("Gaming.Perception")

# Import mc_log from agent module
from .agent import mc_log, log_embodiment


class PerceptionMixin:
    """
    Mixin providing perception and verification methods for GamingAgent.
    
    Requires: self.bridge, self._pending_chats, self._last_position, self._stuck_counter
    """

    async def _observe(self) -> Dict:
        """Gather current game state including visual perception."""
        # 1. Get status
        mc_log("DEBUG", "OBSERVE_STEP_1_GET_STATUS_START")
        t1 = time.time()
        status = await self.bridge.get_status()
        mc_log("DEBUG", "OBSERVE_STEP_1_GET_STATUS_DONE", elapsed_ms=int((time.time()-t1)*1000), success=status.success)
        
        # 2. Get nearby entities
        mc_log("DEBUG", "OBSERVE_STEP_2_GET_NEARBY_START")
        t2 = time.time()
        nearby = await self.bridge.execute("get_nearby")
        mc_log("DEBUG", "OBSERVE_STEP_2_GET_NEARBY_DONE", elapsed_ms=int((time.time()-t2)*1000), success=nearby.success)
        
        # 3. Get time info
        mc_log("DEBUG", "OBSERVE_STEP_3_GET_TIME_START")
        t3 = time.time()
        time_info = await self.bridge.execute("get_time")
        mc_log("DEBUG", "OBSERVE_STEP_3_GET_TIME_DONE", elapsed_ms=int((time.time()-t3)*1000), success=time_info.success)
        
        # 4. Visual perception - capture screenshot (NON-BLOCKING, graceful failure)
        mc_log("DEBUG", "OBSERVE_STEP_4_SCREENSHOT_START")
        t4 = time.time()
        screenshot_b64 = None
        try:
            screenshot_b64 = await asyncio.wait_for(
                self.bridge.get_screenshot(),
                timeout=5.0  # Hard 5s limit to prevent blocking
            )
            if screenshot_b64:
                mc_log("DEBUG", "OBSERVE_STEP_4_SCREENSHOT_DONE", elapsed_ms=int((time.time()-t4)*1000), size=len(screenshot_b64))
            else:
                mc_log("DEBUG", "OBSERVE_STEP_4_SCREENSHOT_DONE", elapsed_ms=int((time.time()-t4)*1000), size=0)
        except asyncio.TimeoutError:
            mc_log("WARNING", "OBSERVE_STEP_4_SCREENSHOT_TIMEOUT", elapsed_ms=int((time.time()-t4)*1000))
        except Exception as e:
            mc_log("WARNING", "OBSERVE_STEP_4_SCREENSHOT_ERROR", elapsed_ms=int((time.time()-t4)*1000), error=str(e))
        
        mc_log("DEBUG", "OBSERVE_STEP_5_BUILD_STATE_START")
        state = {
            "health": status.data.get("health") if status.success else 20,
            "food": status.data.get("food") if status.success else 20,
            "position": status.data.get("position") if status.success else {},
            "inventory": status.data.get("inventory", [])[:10] if status.success else [],
            "nearby_entities": nearby.data.get("entities", []) if nearby.success else [],
            "hostiles_nearby": nearby.data.get("hostiles_nearby", False) if nearby.success else False,
            "is_day": time_info.data.get("isDay", True) if time_info.success else True,
            "pending_chats": self._pending_chats.copy(),
            "screenshot": screenshot_b64,  # Base64 JPEG for vision model
        }
        
        # Log pending chats if any
        if self._pending_chats:
            mc_log("INFO", "OBSERVE_PENDING_CHATS", count=len(self._pending_chats), 
                   chats=str(self._pending_chats)[:100])
        
        # Clear processed chats
        self._pending_chats.clear()
        
        mc_log("DEBUG", "OBSERVE_STEP_5_BUILD_STATE_DONE")
        return state
    
    def _build_reflexes(self, state: Dict) -> List[Dict]:
        """Build reflex actions to run during inference."""
        chain = []
        
        # Always look around
        chain.append({"command": "look_around", "params": {}})
        
        # Eat if hungry
        if state.get("food", 20) < 18:
            chain.append({"command": "maintain_status", "params": {}})
        
        # Defend if hostiles nearby
        if state.get("hostiles_nearby"):
            chain.append({"command": "defend", "params": {}})
        
        # Collect nearby drops
        chain.append({"command": "collect_drops", "params": {}})
        
        # Look around again
        chain.append({"command": "look_around", "params": {}})
        
        return chain
    
    def _check_stuck(self, current_pos: Dict) -> bool:
        """
        Check if bot is stuck (not moving for multiple cycles).
        
        Returns True if stuck (3+ cycles with < 1 block movement).
        """
        if not current_pos or not self._last_position:
            self._last_position = current_pos
            return False
        
        # Calculate distance moved
        dx = current_pos.get("x", 0) - self._last_position.get("x", 0)
        dy = current_pos.get("y", 0) - self._last_position.get("y", 0)
        dz = current_pos.get("z", 0) - self._last_position.get("z", 0)
        distance = (dx**2 + dy**2 + dz**2) ** 0.5
        
        if distance < 1.0:  # Hasn't moved 1 block
            self._stuck_counter += 1
            mc_log("DEBUG", "STUCK_CHECK", distance=distance, counter=self._stuck_counter)
        else:
            self._stuck_counter = 0
        
        self._last_position = current_pos
        return self._stuck_counter >= 3  # Stuck for 3 cycles
    
    async def _unstuck(self) -> str:
        """
        Recovery actions when bot is stuck.
        
        Returns: Action to take for recovery
        """
        import random
        mc_log("WARNING", "BOT_STUCK_DETECTED", counter=self._stuck_counter)
        log_embodiment("stuck", "I'm stuck! Trying to get unstuck...")
        
        # Reset counter
        self._stuck_counter = 0
        
        # Try different unstuck strategies
        strategy = random.choice(["jump", "turn", "explore", "dig"])
        
        if strategy == "jump":
            await self.bridge.execute("jump")
            return "explore"
        elif strategy == "turn":
            yaw = random.randint(-180, 180)
            await self.bridge.execute("look", {"yaw": yaw, "pitch": 0})
            return "explore"
        elif strategy == "explore":
            return "explore"
        else:
            await self.bridge.execute("dig_forward")
            return "explore"

    async def _execute_reflexes(self, chain: List[Dict]):
        """Fire predictive chain in background."""
        try:
            await self.bridge.execute("execute_predictive_chain", {"chain": chain})
        except Exception as e:
            logger.error(f"Reflex chain error: {e}")

    async def _verify_action(self, action: str, before_inv: Dict, after_inv: Dict, before_pos: Dict = None, after_pos: Dict = None) -> bool:
        """
        Verify if an action succeeded by comparing before/after state.
        
        Returns True if action appears successful.
        """
        parts = action.strip().split()
        if not parts:
            return True  # No action to verify
        
        cmd = parts[0].lower()
        target = parts[1] if len(parts) > 1 else None
        
        if cmd in ("collect", "mine", "get", "obtain") and target:
            # Check if we got more of the target item
            before_count = before_inv.get(target, 0)
            after_count = after_inv.get(target, 0)
            success = after_count > before_count
            mc_log("DEBUG", "VERIFY_COLLECT", item=target, before=before_count, after=after_count, success=success)
            return success
        
        elif cmd == "craft" and target:
            before_count = before_inv.get(target, 0)
            after_count = after_inv.get(target, 0)
            success = after_count > before_count
            mc_log("DEBUG", "VERIFY_CRAFT", item=target, before=before_count, after=after_count, success=success)
            return success
        
        elif cmd == "smelt" and target:
            outputs = {
                "iron_ore": "iron_ingot",
                "gold_ore": "gold_ingot",
                "raw_iron": "iron_ingot",
                "raw_gold": "gold_ingot",
                "raw_copper": "copper_ingot",
                "cobblestone": "stone",
                "sand": "glass",
            }
            output_item = outputs.get(target, target)
            before_count = before_inv.get(output_item, 0)
            after_count = after_inv.get(output_item, 0)
            success = after_count > before_count
            mc_log("DEBUG", "VERIFY_SMELT", input=target, output=output_item, success=success)
            return success
        
        elif cmd in ("goto", "explore", "follow"):
            if before_pos and after_pos:
                dx = after_pos.get("x", 0) - before_pos.get("x", 0)
                dy = after_pos.get("y", 0) - before_pos.get("y", 0)
                dz = after_pos.get("z", 0) - before_pos.get("z", 0)
                distance = (dx**2 + dy**2 + dz**2) ** 0.5
                success = distance >= 2.0
                mc_log("DEBUG", "VERIFY_MOVE", cmd=cmd, distance=round(distance, 1), success=success)
                return success
            return True
        
        # For other commands, assume success
        return True

    async def _get_inventory_counts(self) -> Dict[str, int]:
        """Get current inventory as {item_name: count} dict."""
        status = await self.bridge.get_status()
        if not status.success:
            return {}
        inv = {}
        for item in status.data.get("inventory", []):
            name = item.get("name", "unknown")
            count = item.get("count", 1)
            inv[name] = inv.get(name, 0) + count
        return inv
