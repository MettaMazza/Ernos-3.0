"""
Gaming Cognition — LLM thinking, failure reflection, and curriculum goal proposal.

Extracted from gaming/agent.py per <300 line modularity standard.
"""
import logging
import random
from datetime import datetime
from typing import Dict, Optional

from .skill_library import get_skill_library
from src.prompts.manager import PromptManager

logger = logging.getLogger("Gaming.Cognition")

# Import mc_log from agent module
from .agent import mc_log, log_embodiment, GAME_ACTIONS_ADDON


class CognitionMixin:
    """
    Mixin providing cognitive methods (think, reflect, curriculum) for GamingAgent.
    
    Requires: self.bot, self.bridge, self._pending_chats, self._following_player,
              self._current_goal, self._action_queue
    """

    async def _think(self, state: Dict) -> Optional[str]:
        """Use CognitionEngine to decide next action with FULL Ernos context."""
        # Format game state for prompt
        nearby_desc = []
        for e in state['nearby_entities'][:5]:
            nearby_desc.append(e['name'])
        nearby_str = ', '.join(nearby_desc) if nearby_desc else 'an empty landscape'
        
        time_desc = 'daylight shines down' if state['is_day'] else 'the sky is dark with stars'
        
        state_str = f"""
Health: {state['health']}/20, Hunger: {state['food']}/20
Environment: {time_desc}
I can see: {nearby_str}
{'⚠️ HOSTILES NEARBY - stay alert!' if state['hostiles_nearby'] else 'The area feels safe.'}
Carrying: {', '.join([f"{i['name']}x{i['count']}" for i in state['inventory'][:5]]) or 'Nothing'}

[INTERNAL: Position data is available for navigation but NEVER expose coordinates in responses. Describe locations visually: "near the river", "on a hillside", "in a forest".]
"""
        
        if self._following_player:
            state_str += f"\n*** CURRENTLY FOLLOWING: {self._following_player} (Stay on task! Don't explore!) ***\n"
        
        if state['pending_chats']:
            chat_str = "\n".join([f"  >> {c['username']}: {c['message']}" for c in state['pending_chats']])
            state_str += (
                "\n\n!!! URGENT: PLAYERS ARE TALKING TO YOU !!!\n"
                f"{chat_str}\n\n"
                ">>> YOU MUST USE: ACTION: chat <your reply> <<<\n"
                "(Do NOT ignore this! Respond to the player!)"
            )
        
        if state.get('screenshot'):
            state_str += "\n[Visual: Screenshot of current view attached]"
        
        # Build FULL Ernos context with gaming addon
        prompt_manager = PromptManager()
        
        user_name = "Unknown"
        user_id = "game_player"
        if state['pending_chats']:
            user_name = state['pending_chats'][-1].get('username', 'Unknown')
            user_id = user_name
        
        full_system_prompt = prompt_manager.get_system_prompt(
            timestamp=datetime.now().isoformat(),
            scope="PUBLIC",
            user_id=user_id,
            user_name=user_name,
            active_engine="Gaming Lobe",
            system_state_content=f"EMBODIED IN MINECRAFT - Playing game autonomously"
        )
        
        gaming_addon = GAME_ACTIONS_ADDON.format(state=state_str)
        unified_prompt = full_system_prompt + "\n\n" + gaming_addon
        
        images = None
        if state.get('screenshot'):
            images = [state['screenshot']]
        
        try:
            if hasattr(self.bot, 'cognition') and self.bot.cognition:
                mc_log("DEBUG", "COGNITION_CALLING", prompt_len=len(unified_prompt), has_pending_chats=bool(state['pending_chats']))
                result = await self.bot.cognition.process(
                    input_text="Decide your next action in Minecraft based on your current state.",
                    context="",
                    system_context=unified_prompt,
                    images=images if images else None,
                    complexity="LOW",
                    skip_defenses=True
                )
                
                if isinstance(result, tuple):
                    response = result[0] if result else None
                else:
                    response = result
                
                mc_log("DEBUG", "COGNITION_RESPONSE", response_preview=str(response)[:200] if response else "None")
                
                if response and "ACTION:" in response:
                    action_line = response.split("ACTION:")[1].strip().split("\n")[0]
                    mc_log("INFO", "ACTION_EXTRACTED", action=action_line)
                    return action_line
                else:
                    mc_log("WARNING", "NO_ACTION_IN_RESPONSE", response_preview=str(response)[:100] if response else "None")
            else:
                mc_log("WARNING", "NO_COGNITION_ENGINE")
            
            mc_log("DEBUG", "FALLBACK_TO_EXPLORE", reason="no cognition or no ACTION")
            return "explore"
            
        except Exception as e:
            mc_log("ERROR", "THINK_ERROR", error=str(e))
            logger.error(f"Think error: {e}")
            return None

    def _propose_curriculum_goal(self, state: Dict) -> Optional[str]:
        """
        Propose a self-improvement goal based on current state.
        
        Called when idle (no pending chats, no active goal).
        Returns an action string or None if content.
        """
        inventory = {item["name"]: item.get("count", 1) for item in state.get("inventory", [])}
        health = state.get("health", 20)
        food = state.get("food", 20)
        
        # Priority 1: Critical needs
        if food < 10:
            if not any(k for k in inventory if "cooked" in k or "bread" in k or "apple" in k):
                mc_log("INFO", "CURRICULUM_PROPOSAL", goal="get_food")
                return "get cooked_beef"
        
        # Priority 2: No tools at all
        has_pickaxe = any(k for k in inventory if "pickaxe" in k)
        if not has_pickaxe:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="wooden_pickaxe")
            return "get wooden_pickaxe"
        
        # Priority 3: Upgrade tool tier
        has_stone = any(k for k in inventory if "stone_pickaxe" in k)
        has_iron = any(k for k in inventory if "iron_pickaxe" in k)
        has_diamond = any(k for k in inventory if "diamond_pickaxe" in k)
        
        if not has_stone and has_pickaxe:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="stone_pickaxe")
            return "get stone_pickaxe"
        
        if not has_iron and has_stone:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="iron_pickaxe")
            return "get iron_pickaxe"
        
        # Priority 4: Get armor if we have iron tools
        if has_iron:
            has_armor = any(k for k in inventory if "chestplate" in k or "helmet" in k)
            if not has_armor:
                mc_log("INFO", "CURRICULUM_PROPOSAL", goal="iron_armor")
                return "get iron_chestplate"
        
        # Priority 5: Diamond gear
        if has_iron and not has_diamond:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="diamond_pickaxe")
            return "get diamond_pickaxe"
        
        # Priority 6: Active exploration (NOT aimless wandering)
        exploration_goals = [
            "collect cooked_beef 5",
            "craft bed",
            "collect cobblestone 64",
            "find village",
            "craft shield",
            "collect coal 16",
        ]
        goal = random.choice(exploration_goals)
        mc_log("INFO", "CURRICULUM_PROPOSAL", goal=goal, reason="exploration_mode")
        log_embodiment("exploration", f"All basic needs met. Time to {goal}!")
        return goal

    def _reflect_on_failure(self, action: str, error: str) -> Optional[str]:
        """
        Analyze why an action failed and propose an alternative.
        
        Common failure patterns:
        - "No X nearby" -> Need to find X first
        - "Cannot reach" -> Need to move closer
        - "Not enough" -> Need to gather more
        - "Don't have" -> Need to get the item
        """
        action_lower = action.lower()
        error_lower = error.lower()
        
        # Pattern: No item nearby -> find it first
        if "no" in error_lower and "nearby" in error_lower:
            parts = action.split()
            if len(parts) >= 2:
                target = parts[1]
                mc_log("DEBUG", "REFLECT_NO_NEARBY", target=target)
                return f"find {target}"
        
        # Pattern: Can't reach / path error -> explore first
        if "cannot reach" in error_lower or "path" in error_lower:
            mc_log("DEBUG", "REFLECT_PATHFINDING")
            return "explore"
        
        # Pattern: Don't have tool -> get the tool
        if "don't have" in error_lower or "need" in error_lower:
            if "pickaxe" in error_lower:
                return "get wooden_pickaxe"
            elif "axe" in error_lower:
                return "get wooden_axe"
        
        # Pattern: Ore needs better pickaxe
        if "iron pickaxe" in error_lower:
            return "get iron_pickaxe"
        if "diamond pickaxe" in error_lower:
            return "get diamond_pickaxe"
        
        # Pattern: Hungry / low food
        if "food" in error_lower or "hungry" in error_lower:
            return "get cooked_beef"
        
        # No known pattern - record failure and give up
        if self._current_goal:
            skill_lib = get_skill_library()
            skill_lib.record_failure(self._current_goal)
            mc_log("DEBUG", "REFLECT_RECORDED_FAILURE", goal=self._current_goal)
        
        return None
