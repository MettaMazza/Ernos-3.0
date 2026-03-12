"""
Gaming Cognition — LLM thinking, failure reflection, and curriculum goal proposal.

Extracted from gaming/agent.py per <300 line modularity standard.
"""
import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional

from .skill_library import get_skill_library
from .tech_tree import resolve_item, RECIPES, RECIPE_YIELDS
from src.prompts.manager import PromptManager

logger = logging.getLogger("Gaming.Cognition")

# Import mc_log from agent module
from .utils import mc_log, log_embodiment, GAME_ACTIONS_ADDON


class VirtualInventory:
    """Simulates inventory changes for precognition validation."""
    def __init__(self, initial_items: List[Dict]):
        self.inventory = {resolve_item(i['name']): i.get('count', 1) for i in initial_items}

    def simulate(self, action: str) -> bool:
        parts = action.lower().split()
        if not parts: return True
        cmd = parts[0]
        
        if cmd in ['collect', 'get', 'mine'] and len(parts) >= 2:
            item = resolve_item(parts[1])
            count = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            # Collection gain is literal, not multiplied by crafting yield
            self.inventory[item] = self.inventory.get(item, 0) + count
            return True
            
        if cmd == 'craft' and len(parts) >= 2:
            item = resolve_item(parts[1])
            count = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            if item not in RECIPES: return True 
            
            import math
            yield_count = RECIPE_YIELDS.get(item, 1)
            # Calculate runs needed to reach target count
            runs = math.ceil(count / yield_count)
            
            # Verification phase
            for ing, ing_count in RECIPES[item]:
                total_needed = ing_count * runs
                if self.inventory.get(ing, 0) < total_needed:
                    return False
            
            # Execution phase: consume ingredients and produce yield
            for ing, ing_count in RECIPES[item]:
                self.inventory[ing] -= (ing_count * runs)
            
            self.inventory[item] = self.inventory.get(item, 0) + (runs * yield_count)
            return True
            
        if cmd == 'smelt' and len(parts) >= 2:
            from .tech_tree import SMELTING
            output_item = resolve_item(parts[1])
            # Reverse lookup for input ore
            input_ore = next((k for k, v in SMELTING.items() if k == output_item), None)
            if not input_ore: return True # Not a smelting recipe
            
            input_item = SMELTING[output_item]
            if self.inventory.get(input_item, 0) < 1:
                return False
                
            self.inventory[input_item] -= 1
            self.inventory[output_item] = self.inventory.get(output_item, 0) + 1
            return True
        return True

class CognitionMixin:
    """
    Mixin providing cognitive methods (think, reflect, curriculum) for GamingAgent.
    
    Requires: self.bot, self.bridge, self._pending_chats, self._following_player,
              self._current_goal, self._action_queue
    """

    async def _think(self, state: Dict):
        """Use CognitionEngine to decide next action with FULL Ernos context.
        
        Returns:
            Tuple of (action_str, precognition_list) where:
            - action_str: The primary action to execute now (or None)
            - precognition_list: List of action strings for the precognition queue
        """
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
        
        # Inject failure context so LLM knows what ISN'T working (Issues 3 & 4)
        if hasattr(self, '_consecutive_fail_count') and self._consecutive_fail_count > 0:
            state_str += f"\n⚠️ CONSECUTIVE FAILURES: '{self._consecutive_fail_action}' has failed {self._consecutive_fail_count} time(s). Try something DIFFERENT.\n"
        if hasattr(self, '_follow_fail_count') and self._follow_fail_count > 0:
            state_str += f"\n⚠️ FOLLOW FAILURES: Following player has failed {self._follow_fail_count} time(s). They may be in spectator mode or unreachable. Consider doing something independent.\n"
        if hasattr(self, '_recent_failures') and self._recent_failures:
            recent = self._recent_failures[-5:]
            state_str += f"\n⚠️ RECENT FAILED ACTIONS: {', '.join(recent)}. DO NOT retry these exact actions.\n"
        
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
        
        # Default safety precognition (used if LLM provides none)
        default_precog = ["look_around", "defend", "collect_drops", "look_around"]
        
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
                
                actions = []
                precognition = default_precog
                
                if response:
                    # Reusable chat-aware comma splitter
                    def _smart_split(line):
                        """Split comma-separated actions without breaking chat messages."""
                        raw_parts = [a.strip() for a in line.split(",") if a.strip()]
                        result = []
                        i = 0
                        while i < len(raw_parts):
                            part = raw_parts[i]
                            if part.lower().startswith("chat "):
                                chat_parts = [part]
                                i += 1
                                while i < len(raw_parts):
                                    next_word = raw_parts[i].split()[0].lower() if raw_parts[i].split() else ""
                                    known_cmds = {"follow", "scan", "collect", "explore", "goto", "find",
                                                  "craft", "mine", "defend", "eat", "farm", "harvest",
                                                  "chat", "attack", "equip", "build", "place", "sleep",
                                                  "look_around", "maintain_status", "store", "take"}
                                    if next_word in known_cmds:
                                        break
                                    chat_parts.append(raw_parts[i])
                                    i += 1
                                result.append(", ".join(chat_parts))
                            else:
                                result.append(part)
                                i += 1
                        return result
                    
                    # Parse ACTION with VirtualInventory validation
                    v_inv = VirtualInventory(state.get('inventory', []))
                    if "ACTION:" in response:
                        action_line = response.split("ACTION:")[1].strip().split("\n")[0]
                        raw_actions = _smart_split(action_line)
                        
                        validated_actions = []
                        for act in raw_actions:
                            if v_inv.simulate(act):
                                validated_actions.append(act)
                            else:
                                mc_log("DEBUG", "PRIMARY_ACTION_PRUNED", action=act, reason="insufficient resources")
                                break # Stop primary chain at first impossible step
                        
                        actions = validated_actions
                        mc_log("INFO", "ACTIONS_EXTRACTED", count=len(actions), actions=actions[:5])
                    
                    # Parse PRECOGNITION
                    if "PRECOGNITION:" in response:
                        precog_line = response.split("PRECOGNITION:")[1].strip().split("\n")[0]
                        raw_precog = _smart_split(precog_line)
                        
                        # State Simulation Validation
                        v_inv = VirtualInventory(state.get('inventory', []))
                        validated = []
                        for p_act in raw_precog:
                            if v_inv.simulate(p_act):
                                validated.append(p_act)
                            else:
                                mc_log("DEBUG", "PRECOG_STEP_PRUNED", action=p_act, reason="insufficient resources in predicted state")
                                break # Stop chain at first impossible step
                        
                        precognition = validated
                        mc_log("INFO", "PRECOGNITION_EXTRACTED", count=len(precognition), actions=precognition[:5])
                    else:
                        mc_log("DEBUG", "NO_PRECOGNITION_IN_RESPONSE", using="default_safety_reflexes")
                
                if not actions:
                    mc_log("WARNING", "NO_ACTION_IN_RESPONSE", response_preview=str(response)[:100] if response else "None")
                    mc_log("DEBUG", "FALLBACK_TO_EXPLORE", reason="no cognition or no ACTION")
                    actions = ["explore"]
                
                return (actions, precognition)
            else:
                mc_log("WARNING", "NO_COGNITION_ENGINE")
            
            return ("explore", default_precog)
            
        except Exception as e:
            mc_log("ERROR", "THINK_ERROR", error=str(e))
            logger.error(f"Think error: {e}")
            return (None, default_precog)

    async def _quick_llm_call(self, prompt: str) -> str:
        """Lightweight LLM call for reflection/curriculum (no full system context)."""
        try:
            if hasattr(self.bot, 'cognition') and self.bot.cognition:
                result = await self.bot.cognition.process(
                    input_text=prompt,
                    context="",
                    system_context="You are a concise Minecraft gameplay analyst. Reply ONLY with the requested JSON format.",
                    complexity="LOW",
                    skip_defenses=True
                )
                if isinstance(result, tuple):
                    return str(result[0]) if result[0] else ""
                return str(result) if result else ""
        except Exception as e:
            mc_log("WARNING", "QUICK_LLM_CALL_FAILED", error=str(e))
        return ""

    def _get_discovered_items(self) -> set:
        """Get set of all unique items ever obtained (from skill library + current inventory)."""
        discovered = set()
        # From skill library
        skill_lib = get_skill_library()
        for skill in skill_lib.get_all():
            if skill.success_count > 0:
                discovered.add(skill.goal)
        # From discovery tracker on agent
        if hasattr(self, '_discovered_items'):
            discovered.update(self._discovered_items)
        return discovered

    def _propose_curriculum_goal(self, state: Dict) -> Optional[str]:
        """
        Propose a self-improvement goal based on current state.
        
        Uses fast-path checks for critical needs, then LLM-driven novelty
        proposal for strategic goals.
        """
        inventory = {item["name"]: item.get("count", 1) for item in state.get("inventory", [])}
        health = state.get("health", 20)
        food = state.get("food", 20)
        
        # Priority 1: Critical needs (fast path — no LLM needed)
        if food < 10:
            if not any(k for k in inventory if "cooked" in k or "bread" in k or "apple" in k):
                mc_log("INFO", "CURRICULUM_PROPOSAL", goal="get_food")
                return "get cooked_beef"
        
        # Priority 2: No tools at all (fast path)
        has_pickaxe = any(k for k in inventory if "pickaxe" in k)
        if not has_pickaxe:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="wooden_pickaxe")
            return "get wooden_pickaxe"
        
        # Priority 3: Upgrade tool tier (fast path)
        has_stone = any(k for k in inventory if "stone_pickaxe" in k)
        has_iron = any(k for k in inventory if "iron_pickaxe" in k)
        has_diamond = any(k for k in inventory if "diamond_pickaxe" in k)
        
        if not has_stone and has_pickaxe:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="stone_pickaxe")
            return "get stone_pickaxe"
        
        if not has_iron and has_stone:
            mc_log("INFO", "CURRICULUM_PROPOSAL", goal="iron_pickaxe")
            return "get iron_pickaxe"
        
        # Priority 4: LLM-driven novelty goal
        # Track what we've already done and ask the LLM for something NEW
        discovered = self._get_discovered_items()
        inv_str = ", ".join(f"{k}x{v}" for k, v in sorted(inventory.items())[:20]) or "nothing"
        disc_str = ", ".join(sorted(discovered)[:20]) or "nothing yet"
        tools_str = ", ".join(k for k in inventory if any(t in k for t in ["pickaxe", "axe", "sword", "shovel"])) or "none"
        
        prompt = (
            f"Propose ONE specific Minecraft goal that advances the tech tree or explores new things.\n\n"
            f"Current inventory: {inv_str}\n"
            f"Tools: {tools_str}\n"
            f"Already discovered/crafted: {disc_str}\n"
            f"Health: {health}/20, Food: {food}/20\n\n"
            f"Reply as JSON: {{\"goal\": \"exact action string\", \"reason\": \"one sentence why\"}}\n"
            f"Action must start with: get, craft, find, collect, explore, or build.\n"
            f"Choose something NEW that hasn't been done yet."
        )
        
        try:
            # Use asyncio to run the LLM call from sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context — schedule as a task
                import concurrent.futures
                future = asyncio.ensure_future(self._quick_llm_call(prompt))
                # Can't await here in sync — fall back to heuristic
                raise RuntimeError("sync context")
            else:
                response = loop.run_until_complete(self._quick_llm_call(prompt))
        except Exception:
            # Fall back to heuristic curriculum
            return self._curriculum_fallback(state, inventory, has_iron, has_diamond)
        
        try:
            # Parse JSON from LLM response
            if "{" in response and "}" in response:
                json_str = response[response.index("{"):response.rindex("}")+1]
                result = json.loads(json_str)
                goal = result.get("goal", "").strip()
                reason = result.get("reason", "")
                if goal:
                    mc_log("INFO", "CURRICULUM_LLM_PROPOSAL", goal=goal, reason=reason[:60], discovered_count=len(discovered))
                    log_embodiment("curriculum", f"Setting new goal: {goal} — {reason}")
                    return goal
        except (json.JSONDecodeError, ValueError):
            pass
        
        return self._curriculum_fallback(state, inventory, has_iron, has_diamond)

    def _curriculum_fallback(self, state: Dict, inventory: Dict = None, has_iron: bool = False, has_diamond: bool = False) -> str:
        """Hardcoded curriculum fallback when LLM is unavailable."""
        if inventory is None:
            inventory = {item["name"]: item.get("count", 1) for item in state.get("inventory", [])}
            has_iron = any(k for k in inventory if "iron_pickaxe" in k)
            has_diamond = any(k for k in inventory if "diamond_pickaxe" in k)
        
        if has_iron:
            has_armor = any(k for k in inventory if "chestplate" in k or "helmet" in k)
            if not has_armor:
                return "get iron_chestplate"
        
        if has_iron and not has_diamond:
            return "get diamond_pickaxe"
        
        exploration_goals = [
            "find village", "craft bed", "collect oak_log 10",
            "explore", "craft shield", "farm wheat 3",
            "save_location home", "collect cooked_beef 5",
        ]
        goal = random.choice(exploration_goals)
        mc_log("INFO", "CURRICULUM_PROPOSAL", goal=goal, reason="fallback")
        log_embodiment("exploration", f"All basic needs met. Time to {goal}!")
        return goal

    async def _reflect_on_failure(self, action: str, error: str, state: Dict = None) -> Optional[str]:
        """
        LLM-driven failure analysis — asks WHY before retrying.
        
        Includes failure history to prevent suggesting the same broken retry.
        Falls back to keyword-matching heuristics if LLM is unavailable.
        """
        # Build failure history context
        failure_history = ""
        if hasattr(self, '_recent_failures') and self._recent_failures:
            failure_history = f"\nPrevious failed actions (DO NOT suggest these): {', '.join(self._recent_failures[-5:])}\n"
        
        # Detect reflection loops — if we've failed this exact action 3+ times, abandon goal
        if hasattr(self, '_recent_failures'):
            same_action_count = sum(1 for f in self._recent_failures if f == action)
            if same_action_count >= 3:
                mc_log("WARNING", "REFLECTION_LOOP_DETECTED", action=action, count=same_action_count)
                log_embodiment("reflection_loop", f"I've tried '{action}' {same_action_count} times and it keeps failing. ABANDONING this goal.")
                if self._current_goal:
                    skill_lib = get_skill_library()
                    skill_lib.record_failure(self._current_goal)
                    self._current_goal = None
                    self._action_queue.clear()
                return "explore"  # Force a complete direction change
        
        # Build context for LLM
        inv_summary = "empty"
        if state:
            items = state.get("inventory", [])
            inv_summary = ", ".join(f"{i['name']}x{i.get('count',1)}" for i in items[:15]) or "empty"
        
        prompt = (
            f"A Minecraft action just FAILED. Analyze why and suggest what to do instead.\n\n"
            f"Failed action: {action}\n"
            f"Error message: {error}\n"
            f"Current inventory: {inv_summary}\n"
            f"{failure_history}"
            f"\nReply as JSON: {{\"analysis\": \"brief explanation of root cause\", \"retry_action\": \"exact action string or null\"}}\n"
            f"The retry action MUST be different from the failed action AND from any previously failed actions listed above.\n"
            f"If the failed action needs prerequisites (like planks before a pickaxe), suggest getting those first.\n"
            f"Valid action prefixes: get, craft, collect, find, explore, mine, attack, eat, equip."
        )
        
        # Skip LLM for known-benign failures — use fast heuristic instead
        benign_cmds = {"place", "explore", "wander", "scan"}
        action_cmd = action.split()[0].lower() if action else ""
        if action_cmd in benign_cmds:
            mc_log("DEBUG", "REFLECT_SKIP_LLM", reason=f"benign failure: {action_cmd}")
            return self._reflect_heuristic(action, error)
        
        try:
            response = await asyncio.wait_for(
                self._quick_llm_call(prompt),
                timeout=30.0
            )
            if response and "{" in response and "}" in response:
                json_str = response[response.index("{"):response.rindex("}")+1]
                result = json.loads(json_str)
                retry = result.get("retry_action")
                analysis = result.get("analysis", "")
                mc_log("INFO", "REFLECT_LLM", analysis=analysis[:100], retry=retry)
                log_embodiment("reflection", f"Failed at '{action}': {analysis}. Will try: {retry}")
                if retry and retry.lower() != "null" and retry != action:
                    # Don't suggest something that's also already failed
                    if hasattr(self, '_recent_failures') and retry in self._recent_failures:
                        mc_log("DEBUG", "REFLECT_RETRY_ALREADY_FAILED", retry=retry)
                        return "explore"  # Fallback to something completely different
                    return retry
        except asyncio.TimeoutError:
            mc_log("WARNING", "REFLECT_LLM_TIMEOUT", action=action)
        except Exception as e:
            mc_log("WARNING", "REFLECT_LLM_FAILED", error=str(e))
        
        # Heuristic fallback
        return self._reflect_heuristic(action, error)

    def _reflect_heuristic(self, action: str, error: str) -> Optional[str]:
        """Keyword-based failure reflection fallback."""
        error_lower = error.lower()
        
        if "no" in error_lower and "nearby" in error_lower:
            parts = action.split()
            if len(parts) >= 2:
                mc_log("DEBUG", "REFLECT_HEURISTIC_NO_NEARBY", target=parts[1])
                return f"find {parts[1]}"
        
        if "cannot reach" in error_lower or "path" in error_lower:
            return "explore"
        
        if "no recipe" in error_lower or "missing" in error_lower or "resources" in error_lower:
            # Likely needs prerequisites — use hierarchical planner
            parts = action.split()
            if len(parts) >= 2 and parts[0] == "craft":
                return f"get {parts[1]}"
        
        if "don't have" in error_lower or "need" in error_lower:
            if "pickaxe" in error_lower:
                return "get wooden_pickaxe"
            elif "axe" in error_lower:
                return "get wooden_axe"
        
        if "iron pickaxe" in error_lower:
            return "get iron_pickaxe"
        if "diamond pickaxe" in error_lower:
            return "get diamond_pickaxe"
        
        if "food" in error_lower or "hungry" in error_lower:
            return "get cooked_beef"
        
        # Record failure
        if self._current_goal:
            skill_lib = get_skill_library()
            skill_lib.record_failure(self._current_goal)
            mc_log("DEBUG", "REFLECT_RECORDED_FAILURE", goal=self._current_goal)
        
        return None
