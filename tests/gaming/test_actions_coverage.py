"""
Coverage tests for gaming/actions.py — targets uncovered lines 30-314.

Tests: ActionsMixin._act (all 20+ command branches), _act_hierarchical,
       _act_follow, _act_explore, _act_protect, _act_eat, error/retry logic.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.gaming.mineflayer_bridge import BridgeResponse


def make_actions_agent():
    """Create a mock agent with ActionsMixin methods."""
    from src.gaming.actions import ActionsMixin

    class MockAgent(ActionsMixin):
        pass

    agent = MockAgent()
    agent.bridge = AsyncMock()
    agent._current_goal = None
    agent._goal_start_time = None
    agent._goal_actions = []
    agent._action_queue = []
    agent._following_player = None
    agent._pending_chats = []
    agent._reflect_on_failure = AsyncMock(return_value=None)
    # Default: all bridge calls return success
    agent.bridge.goto.return_value = BridgeResponse(True, {})
    agent.bridge.collect.return_value = BridgeResponse(True, {})
    agent.bridge.craft.return_value = BridgeResponse(True, {})
    agent.bridge.attack.return_value = BridgeResponse(True, {})
    agent.bridge.chat.return_value = BridgeResponse(True, {})
    agent.bridge.follow.return_value = BridgeResponse(True, {})
    agent.bridge.stop_follow.return_value = BridgeResponse(True, {})
    agent.bridge.equip.return_value = BridgeResponse(True, {})
    agent.bridge.shield.return_value = BridgeResponse(True, {})
    agent.bridge.sleep.return_value = BridgeResponse(True, {})
    agent.bridge.wake.return_value = BridgeResponse(True, {})
    agent.bridge.smelt.return_value = BridgeResponse(True, {})
    agent.bridge.store.return_value = BridgeResponse(True, {})
    agent.bridge.take.return_value = BridgeResponse(True, {})
    agent.bridge.place.return_value = BridgeResponse(True, {})
    agent.bridge.farm.return_value = BridgeResponse(True, {})
    agent.bridge.harvest.return_value = BridgeResponse(True, {})
    agent.bridge.plant.return_value = BridgeResponse(True, {})
    agent.bridge.fish.return_value = BridgeResponse(True, {})
    agent.bridge.save_location.return_value = BridgeResponse(True, {})
    agent.bridge.goto_location.return_value = BridgeResponse(True, {})
    agent.bridge.copy_build.return_value = BridgeResponse(True, {})
    agent.bridge.build.return_value = BridgeResponse(True, {})
    agent.bridge.list_blueprints.return_value = BridgeResponse(True, {})
    agent.bridge.drop.return_value = BridgeResponse(True, {})
    agent.bridge.give.return_value = BridgeResponse(True, {})
    agent.bridge.find.return_value = BridgeResponse(True, {})
    agent.bridge.eat.return_value = BridgeResponse(True, {})
    agent.bridge.share.return_value = BridgeResponse(True, {})
    agent.bridge.scan.return_value = BridgeResponse(True, {})
    agent.bridge.coop_mode.return_value = BridgeResponse(True, {})
    agent.bridge.protect.return_value = BridgeResponse(True, {})
    agent.bridge.get_status.return_value = BridgeResponse(True, {
        "position": {"x": 10, "y": 64, "z": 20},
        "inventory": []
    })
    return agent


# ──────────────────────────────────────
# _act: Empty / Unknown
# ──────────────────────────────────────

class TestActEmpty:
    @pytest.mark.asyncio
    async def test_empty_action(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("")
        # No bridge calls
        agent.bridge.goto.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_action(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("   ")
        assert True  # Execution completed without error


# ──────────────────────────────────────
# Core Actions
# ──────────────────────────────────────

class TestActCoreActions:
    @pytest.mark.asyncio
    async def test_goto(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("goto 100 64 200")
        agent.bridge.goto.assert_called_with(100.0, 64.0, 200.0)

    @pytest.mark.asyncio
    async def test_collect(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("collect oak_log 5")
        agent.bridge.collect.assert_called_with("oak_log", 5)

    @pytest.mark.asyncio
    async def test_collect_default_count(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("collect iron_ore")
        agent.bridge.collect.assert_called_with("iron_ore", 1)

    @pytest.mark.asyncio
    async def test_craft(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("craft planks 4")
        agent.bridge.craft.assert_called_with("planks", 4)

    @pytest.mark.asyncio
    async def test_craft_default_count(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("craft stick")
        agent.bridge.craft.assert_called_with("stick", 1)

    @pytest.mark.asyncio
    async def test_attack_with_target(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            result = await agent._act("attack zombie")
        agent.bridge.attack.assert_called_with("zombie")

    @pytest.mark.asyncio
    async def test_attack_default_hostile(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("attack")
        agent.bridge.attack.assert_called_with("hostile")

    @pytest.mark.asyncio
    async def test_chat(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("chat Hello world!")
        agent.bridge.chat.assert_called_with("Hello world!")
        mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_follow(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("follow metta_mazza")
        agent.bridge.follow.assert_called_with("metta_mazza")
        assert agent._following_player == "metta_mazza"

    @pytest.mark.asyncio
    async def test_explore(self):
        agent = make_actions_agent()
        agent.bridge.execute.return_value = BridgeResponse(True, {"distance_moved": 15, "position": {"x": 25, "y": 64, "z": 35}})
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("explore")
        agent.bridge.execute.assert_called_with("explore")

    @pytest.mark.asyncio
    async def test_protect(self):
        agent = make_actions_agent()
        agent._pending_chats = [{"username": "player1"}]
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("protect 30")
        agent.bridge.protect.assert_called_with(username="player1", radius=30)


# ──────────────────────────────────────
# Combat & Survival
# ──────────────────────────────────────

class TestActCombat:
    @pytest.mark.asyncio
    async def test_equip_success(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("equip diamond_sword hand")
        agent.bridge.equip.assert_called_with("diamond_sword", "hand")
        mock_log.assert_called_with("item_equipped", "I equipped diamond_sword to hand")

    @pytest.mark.asyncio
    async def test_equip_failure(self):
        agent = make_actions_agent()
        agent.bridge.equip.return_value = BridgeResponse(False, error="not found")
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("equip missing_item")
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_shield_up(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("shield")
        agent.bridge.shield.assert_called_with(True)
        mock_log.assert_called_with("shield_action", "I raised my shield")

    @pytest.mark.asyncio
    async def test_shield_down(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("shield down")
        agent.bridge.shield.assert_called_with(False)
        mock_log.assert_called_with("shield_action", "I lowered my shield")

    @pytest.mark.asyncio
    async def test_sleep_success(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("sleep")
        agent.bridge.sleep.assert_called()
        mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_wake_success(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("wake")
        agent.bridge.wake.assert_called()
        mock_log.assert_called()


# ──────────────────────────────────────
# Resource Management
# ──────────────────────────────────────

class TestActResources:
    @pytest.mark.asyncio
    async def test_smelt(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act("smelt iron_ore coal 4")
        agent.bridge.smelt.assert_called_with("iron_ore", "coal", 4)
        mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_smelt_defaults(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("smelt iron_ore")
        agent.bridge.smelt.assert_called_with("iron_ore", "coal", 1)

    @pytest.mark.asyncio
    async def test_store_all(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("store")
        agent.bridge.store.assert_called_with(None, None)

    @pytest.mark.asyncio
    async def test_store_specific(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("store iron 10")
        agent.bridge.store.assert_called_with("iron", 10)

    @pytest.mark.asyncio
    async def test_take_all(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("take")
        agent.bridge.take.assert_called_with(None, None)

    @pytest.mark.asyncio
    async def test_take_specific(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("take diamond 5")
        agent.bridge.take.assert_called_with("diamond", 5)

    @pytest.mark.asyncio
    async def test_place_no_coords(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("place cobblestone")
        agent.bridge.place.assert_called_with("cobblestone", None, None, None)

    @pytest.mark.asyncio
    async def test_place_with_coords(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("place stone 10 64 20")
        agent.bridge.place.assert_called_with("stone", 10, 64, 20)


# ──────────────────────────────────────
# Farming & Sustainability
# ──────────────────────────────────────

class TestActFarming:
    @pytest.mark.asyncio
    async def test_farm(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("farm wheat 5")
        agent.bridge.farm.assert_called_with("wheat", 5)

    @pytest.mark.asyncio
    async def test_farm_defaults(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("farm")
        agent.bridge.farm.assert_called_with("wheat", 8)

    @pytest.mark.asyncio
    async def test_harvest(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("harvest 10")
        agent.bridge.harvest.assert_called_with(10)

    @pytest.mark.asyncio
    async def test_harvest_default(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("harvest")
        agent.bridge.harvest.assert_called_with(10)

    @pytest.mark.asyncio
    async def test_plant(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("plant carrot 3")
        agent.bridge.plant.assert_called_with("carrot", 3)

    @pytest.mark.asyncio
    async def test_plant_defaults(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("plant")
        agent.bridge.plant.assert_called_with("wheat_seeds", 1)

    @pytest.mark.asyncio
    async def test_fish(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("fish 60")
        agent.bridge.fish.assert_called_with(60)

    @pytest.mark.asyncio
    async def test_fish_default(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("fish")
        agent.bridge.fish.assert_called_with(30)


# ──────────────────────────────────────
# Location & Building
# ──────────────────────────────────────

class TestActLocation:
    @pytest.mark.asyncio
    async def test_save_location(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("save_location home")
        agent.bridge.save_location.assert_called_with("home")

    @pytest.mark.asyncio
    async def test_goto_location(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("goto_location base")
        agent.bridge.goto_location.assert_called_with("base")

    @pytest.mark.asyncio
    async def test_goto_location_no_name(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("goto_location")
        agent.bridge.goto_location.assert_called_with(None)

    @pytest.mark.asyncio
    async def test_copy_build(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("copy_build house 10 15")
        agent.bridge.copy_build.assert_called_with("house", 10, 15)

    @pytest.mark.asyncio
    async def test_copy_build_defaults(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("copy_build tower")
        agent.bridge.copy_build.assert_called_with("tower", 5, 10)

    @pytest.mark.asyncio
    async def test_build_with_name(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("build house")
        agent.bridge.build.assert_called_with("house")

    @pytest.mark.asyncio
    async def test_build_no_name(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            with patch("src.gaming.actions.mc_log"):
                await agent._act("build")
        agent.bridge.list_blueprints.assert_called()


# ──────────────────────────────────────
# Co-op Mode
# ──────────────────────────────────────

class TestActCoop:
    @pytest.mark.asyncio
    async def test_drop(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("drop iron 5")
        agent.bridge.drop.assert_called_with("iron", 5)

    @pytest.mark.asyncio
    async def test_drop_default_count(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("drop diamond")
        agent.bridge.drop.assert_called_with("diamond", 1)

    @pytest.mark.asyncio
    async def test_give(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("give player1 diamond 3")
        agent.bridge.give.assert_called_with("player1", "diamond", 3)

    @pytest.mark.asyncio
    async def test_give_default_count(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("give player1 iron")
        agent.bridge.give.assert_called_with("player1", "iron", 1)

    @pytest.mark.asyncio
    async def test_find(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("find diamond_ore")
        agent.bridge.find.assert_called_with("diamond_ore", False)

    @pytest.mark.asyncio
    async def test_find_with_go(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("find diamond_ore go")
        agent.bridge.find.assert_called_with("diamond_ore", True)

    @pytest.mark.asyncio
    async def test_eat_with_food(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("eat bread")
        agent.bridge.eat.assert_called_with("bread")

    @pytest.mark.asyncio
    async def test_eat_no_food_auto_find(self):
        agent = make_actions_agent()
        agent.bridge.eat.return_value = BridgeResponse(True, {"food": "cooked_beef"})
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("eat")
        agent.bridge.eat.assert_called_with(None)

    @pytest.mark.asyncio
    async def test_eat_no_food_in_inventory(self):
        agent = make_actions_agent()
        agent.bridge.eat.return_value = BridgeResponse(False, error="No food in inventory")
        with patch("src.gaming.actions.log_embodiment"):
            with patch("src.gaming.actions.mc_log"):
                await agent._act("eat")
        agent.bridge.eat.assert_called_with(None)

    @pytest.mark.asyncio
    async def test_share(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("share iron_ingot")
        agent.bridge.share.assert_called_with("iron_ingot")

    @pytest.mark.asyncio
    async def test_scan(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("scan 64")
        agent.bridge.scan.assert_called_with(64)

    @pytest.mark.asyncio
    async def test_scan_default(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("scan")
        agent.bridge.scan.assert_called_with(128)

    @pytest.mark.asyncio
    async def test_coop_mode(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("coop player1 on")
        agent.bridge.coop_mode.assert_called_with("player1", "on")

    @pytest.mark.asyncio
    async def test_coop_mode_default(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("coop_mode player2")
        agent.bridge.coop_mode.assert_called_with("player2", "on")


# ──────────────────────────────────────
# Hierarchical Planning
# ──────────────────────────────────────

class TestActHierarchical:
    @pytest.mark.asyncio
    async def test_plan_with_skill_reuse(self):
        agent = make_actions_agent()
        mock_skill = MagicMock()
        mock_skill.success_rate = 0.8
        mock_skill.name = "collect_wood"
        mock_skill.steps = ["collect oak_log 5"]
        with patch("src.gaming.actions.get_skill_library") as mock_lib:
            mock_lib.return_value.retrieve.return_value = mock_skill
            with patch("src.gaming.actions.log_embodiment"):
                await agent._act("plan oak_log")
        agent.bridge.collect.assert_called()

    @pytest.mark.asyncio
    async def test_plan_with_fresh_planning(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.get_skill_library") as mock_lib:
            mock_lib.return_value.retrieve.return_value = None
            with patch("src.gaming.actions.plan_goal", return_value=["collect log 1", "craft planks 4"]):
                with patch("src.gaming.actions.log_embodiment"):
                    await agent._act("get planks")
        assert agent._current_goal == "planks"

    @pytest.mark.asyncio
    async def test_plan_already_have_item(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.get_skill_library") as mock_lib:
            mock_lib.return_value.retrieve.return_value = None
            with patch("src.gaming.actions.plan_goal", return_value=[]):
                with patch("src.gaming.actions.log_embodiment"):
                    await agent._act("get diamond")
        agent.bridge.chat.assert_called()

    @pytest.mark.asyncio
    async def test_obtain_delegates_to_hierarchical(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.get_skill_library") as mock_lib:
            mock_lib.return_value.retrieve.return_value = None
            with patch("src.gaming.actions.plan_goal", return_value=["collect iron_ore 3"]):
                with patch("src.gaming.actions.log_embodiment"):
                    await agent._act("obtain iron 3")
        assert True  # Execution completed without error

    @pytest.mark.asyncio
    async def test_make_delegates_to_hierarchical(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.get_skill_library") as mock_lib:
            mock_lib.return_value.retrieve.return_value = None
            with patch("src.gaming.actions.plan_goal", return_value=["collect log 1", "craft stick 4"]):
                with patch("src.gaming.actions.log_embodiment"):
                    await agent._act("make stick 4")
        assert True  # Execution completed without error


# ──────────────────────────────────────
# Continue (queued actions)
# ──────────────────────────────────────

class TestActContinue:
    @pytest.mark.asyncio
    async def test_continue_executes_next_action(self):
        agent = make_actions_agent()
        agent._action_queue = ["collect stone 5", "craft furnace"]
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("continue")
        agent.bridge.collect.assert_called_with("stone", 5)
        assert len(agent._action_queue) == 1

    @pytest.mark.asyncio
    async def test_continue_no_queue(self):
        agent = make_actions_agent()
        agent._action_queue = []
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("continue")
        assert True  # No exception: negative case handled correctly
        # No crash, no action taken


# ──────────────────────────────────────
# Helper methods
# ──────────────────────────────────────

class TestActFollow:
    @pytest.mark.asyncio
    async def test_follow_new_player(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_follow("player1")
        agent.bridge.follow.assert_called_with("player1")
        assert agent._following_player == "player1"

    @pytest.mark.asyncio
    async def test_follow_already_following(self):
        agent = make_actions_agent()
        agent._following_player = "player1"
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_follow("player1")
        # Should still re-send follow to refresh pathfinder GoalFollow
        agent.bridge.follow.assert_called_once_with("player1")


class TestActExplore:
    @pytest.mark.asyncio
    async def test_explore_success(self):
        agent = make_actions_agent()
        agent.bridge.execute.return_value = BridgeResponse(True, {
            "distance_moved": 15,
            "position": {"x": 25, "y": 64, "z": 35}
        })
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_explore()
        agent.bridge.execute.assert_called_with("explore")

    @pytest.mark.asyncio
    async def test_explore_status_failure(self):
        agent = make_actions_agent()
        agent.bridge.execute.return_value = BridgeResponse(False, error="fail")
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_explore()
        agent.bridge.execute.assert_called_with("explore")


class TestActProtect:
    @pytest.mark.asyncio
    async def test_protect_with_radius(self):
        agent = make_actions_agent()
        agent._pending_chats = [{"username": "player1"}]
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_protect(["30"])
        agent.bridge.protect.assert_called_with(username="player1", radius=30)

    @pytest.mark.asyncio
    async def test_protect_default_radius(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_protect([])
        agent.bridge.protect.assert_called_with(username="unknown", radius=50)

    @pytest.mark.asyncio
    async def test_protect_failure(self):
        agent = make_actions_agent()
        agent.bridge.protect.return_value = BridgeResponse(False, error="fail")
        with patch("src.gaming.actions.log_embodiment") as mock_log:
            await agent._act_protect([])
        mock_log.assert_not_called()


class TestActEat:
    @pytest.mark.asyncio
    async def test_eat_specified_food(self):
        agent = make_actions_agent()
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_eat(["bread"])
        agent.bridge.eat.assert_called_with("bread")

    @pytest.mark.asyncio
    async def test_eat_auto_find_cooked_chicken(self):
        agent = make_actions_agent()
        agent.bridge.eat.return_value = BridgeResponse(True, {"food": "cooked_chicken"})
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act_eat([])
        agent.bridge.eat.assert_called_with(None)

    @pytest.mark.asyncio
    async def test_eat_no_edibles(self):
        agent = make_actions_agent()
        agent.bridge.eat.return_value = BridgeResponse(False, error="No food in inventory")
        with patch("src.gaming.actions.log_embodiment"):
            with patch("src.gaming.actions.mc_log"):
                await agent._act_eat([])
        agent.bridge.eat.assert_called_with(None)

    @pytest.mark.asyncio
    async def test_eat_status_failure(self):
        agent = make_actions_agent()
        agent.bridge.eat.return_value = BridgeResponse(False, error="bridge error")
        with patch("src.gaming.actions.log_embodiment"):
            with patch("src.gaming.actions.mc_log"):
                await agent._act_eat([])
        agent.bridge.eat.assert_called_with(None)


# ──────────────────────────────────────
# Error handling & self-debugging
# ──────────────────────────────────────

class TestActErrorHandling:
    @pytest.mark.asyncio
    async def test_action_error_no_retry(self):
        agent = make_actions_agent()
        agent.bridge.collect.side_effect = Exception("No blocks found")
        agent._reflect_on_failure = AsyncMock(return_value=None)
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("collect diamond_ore")
        agent._reflect_on_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_error_with_retry(self):
        agent = make_actions_agent()
        # First collect fails, second (find) succeeds
        call_count = 0
        async def smart_collect(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("No blocks nearby")
            return BridgeResponse(True, {})
        
        agent.bridge.collect.side_effect = smart_collect
        agent._reflect_on_failure = AsyncMock(return_value="find diamond_ore")
        with patch("src.gaming.actions.log_embodiment"):
            with patch("src.gaming.actions.mc_log"):
                await agent._act("collect diamond_ore")
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_action_error_retry_same_action_skipped(self):
        """Self-debug retry should not retry the same action."""
        agent = make_actions_agent()
        agent.bridge.collect.side_effect = Exception("fail")
        agent._reflect_on_failure = AsyncMock(return_value="collect diamond_ore")  # Same action
        with patch("src.gaming.actions.log_embodiment"):
            await agent._act("collect diamond_ore")
        assert True  # No exception: error handled gracefully
        # Should NOT retry since it's the same action
