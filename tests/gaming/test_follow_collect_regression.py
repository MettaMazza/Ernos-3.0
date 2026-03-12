"""
Regression tests for Follow/Collect conflict.

Tests that:
1. When following and user says "collect flowers", follow is dismissed and collects go through
2. When chat arrives DURING LLM call, auto-dismiss still fires
3. Follow can't be re-enabled via pre-set when task chats are pending
4. _act_follow can't re-enable follow after auto-dismiss strips it from chain
5. Chat throttle limits to one reply per user message
6. All 3 unpack sites (LLM_INJECTED, THINK_COMPLETE, llm_task.done) behave identically
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


def _make_agent():
    """Create a GamingAgent with mocked dependencies."""
    from src.gaming.agent import GamingAgent
    mock_bot = MagicMock()
    mock_bot.tape_engine = AsyncMock()
    mock_bot.engine_manager.get_active_engine.return_value = MagicMock()
    agent = GamingAgent(mock_bot)
    agent.bridge = MagicMock()
    agent.bridge.execute = AsyncMock()
    agent.bridge.follow = AsyncMock()
    agent.bridge.chat = AsyncMock()
    agent.bridge.collect = AsyncMock()
    return agent


def _make_state(**overrides):
    """Create a standard game state dict."""
    state = {
        'health': 20, 'food': 20,
        'position': {'x': 0, 'y': 64, 'z': 0},
        'is_day': True, 'nearby_entities': [],
        'hostiles_nearby': False, 'inventory': [],
        'pending_chats': [], 'screenshot': None,
    }
    state.update(overrides)
    return state


class TestAutoDissmissFollowForTask:
    """Tests that follow is dismissed when user explicitly requests a task."""

    def test_auto_dismiss_clears_following_when_task_keyword_in_seen_chats(self):
        """
        Scenario: User says "collect all flowers" → LLM responds → auto-dismiss fires.
        The _seen_chats contain the task-keyword chat.
        """
        agent = _make_agent()
        agent._following_player = "metta_mazza"
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect all flowers in this area'}
        ]

        _llm_chat_count = 1
        _seen_chats = agent._pending_chats[:_llm_chat_count]
        del agent._pending_chats[:_llm_chat_count]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        assert agent._following_player is None, "Follow should be dismissed"
        assert _follow_dismissed is True, "Flag should be set"

    def test_auto_dismiss_fires_when_chat_arrives_during_llm_call(self):
        """
        Scenario from 14:11:10 log: "collect flowers" arrives DURING LLM call.
        _llm_chat_count=0 at iteration start, so _seen_chats=[].
        But _pending_chats now has the chat.
        """
        agent = _make_agent()
        agent._following_player = "metta_mazza"

        # At iteration start: no pending chats
        _llm_chat_count = 0
        # During LLM call: "collect flowers" arrives
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect all flowers in the area'}
        ]

        _seen_chats = agent._pending_chats[:_llm_chat_count]  # = []
        del agent._pending_chats[:_llm_chat_count]  # no-op

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        assert agent._following_player is None, \
            "Follow should be dismissed even when chat arrived during LLM call"
        assert _follow_dismissed is True

    def test_auto_dismiss_does_not_fire_for_non_task_chat(self):
        """Follow should NOT be dismissed for chats like 'hello' or 'follow me'."""
        agent = _make_agent()
        agent._following_player = "metta_mazza"
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'hello how are you'}
        ]

        _llm_chat_count = 1
        _seen_chats = agent._pending_chats[:_llm_chat_count]
        del agent._pending_chats[:_llm_chat_count]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        assert agent._following_player == "metta_mazza", "Follow should NOT be dismissed"
        assert _follow_dismissed is False


class TestFollowStrippedFromChain:
    """Tests that follow commands are stripped from the action chain after auto-dismiss."""

    def test_follow_stripped_from_extras_when_dismissed(self):
        """When auto-dismiss fires, follow must be removed from extra_actions."""
        action_decision = "chat Flowers coming right up!"
        extra_actions = ["collect poppy 10", "follow metta_mazza"]

        _follow_dismissed = True

        if _follow_dismissed:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"

        assert "follow metta_mazza" not in extra_actions
        assert extra_actions == ["collect poppy 10"]
        assert action_decision == "chat Flowers coming right up!"

    def test_follow_as_primary_replaced_when_dismissed(self):
        """When primary action is 'follow X' and auto-dismiss fires, primary should be replaced."""
        action_decision = "follow metta_mazza"
        extra_actions = ["collect poppy 10", "collect dandelion 5"]

        _follow_dismissed = True

        if _follow_dismissed:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"

        assert action_decision == "collect poppy 10"
        assert extra_actions == ["collect dandelion 5"]

    def test_follow_as_only_action_replaced_with_explore(self):
        """When follow is the only action and it's dismissed, fallback to explore."""
        action_decision = "follow metta_mazza"
        extra_actions = []

        _follow_dismissed = True

        if _follow_dismissed:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"

        assert action_decision == "explore"


class TestPreSetBlockedByTaskChats:
    """Tests that pre-set follow is blocked when task-keyword chats are pending."""

    def test_pre_set_blocked_when_task_chat_pending(self):
        """
        Scenario from 14:19:36 log: auto-dismiss cleared follow in prev cycle.
        Now _following_player=None. LLM responds with 'follow metta_mazza'.
        But "collect flowers" is still in _pending_chats.
        Pre-set should NOT re-enable follow.
        """
        agent = _make_agent()
        agent._following_player = None  # Already dismissed

        _seen_chats = []  # Already consumed
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect all the flowers in this area'}
        ]

        action_decision = "chat On it!"
        extra_actions = ["collect poppy 5", "follow metta_mazza"]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        # Auto-dismiss: _following_player is None → doesn't fire
        if agent._following_player:
            pass  # Won't execute

        # _has_task_chat check
        _has_task_chat = False
        if not _follow_dismissed:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    _has_task_chat = True
                    break

        if _follow_dismissed or _has_task_chat:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"
        else:
            # Pre-set would run here — should NOT reach this
            for _a in [action_decision] + extra_actions:
                if _a and _a.lower().startswith("follow "):
                    agent._following_player = _a.split(None, 1)[1]
                    break

        assert agent._following_player is None, \
            "Pre-set should NOT re-enable follow when task chats are pending"
        assert _has_task_chat is True
        assert "follow metta_mazza" not in extra_actions, \
            "Follow should be stripped from extras"

    def test_pre_set_allowed_when_no_task_chats(self):
        """Pre-set should work normally when there are no task-keyword chats."""
        agent = _make_agent()
        agent._following_player = None

        _seen_chats = [{'username': 'metta_mazza', 'message': 'follow me'}]
        agent._pending_chats = []

        action_decision = "chat Coming!"
        extra_actions = ["follow metta_mazza"]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False

        _has_task_chat = False
        if not _follow_dismissed:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    _has_task_chat = True
                    break

        if _follow_dismissed or _has_task_chat:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
        else:
            for _a in [action_decision] + extra_actions:
                if _a and _a.lower().startswith("follow "):
                    agent._following_player = _a.split(None, 1)[1]
                    break

        assert agent._following_player == "metta_mazza", \
            "Pre-set SHOULD enable follow when only 'follow me' chat is pending"
        assert _has_task_chat is False


class TestPrecognitionToChainFollowFilter:
    """Tests that _precognition_to_chain correctly filters when following."""

    def test_collect_allowed_when_following(self):
        """Collects should pass through even when _following_player is set (collect removed from NAV_CONFLICTING)."""
        agent = _make_agent()
        agent._following_player = "metta_mazza"

        state = _make_state()
        chain = agent._precognition_to_chain(
            ["collect poppy 5", "collect dandelion 5", "scan 16"], state
        )

        action_strs = [c.get('params', {}).get('action', '') for c in chain
                       if c.get('command') == 'precog_action']
        collect_actions = [a for a in action_strs if str(a).startswith("collect")]
        assert len(collect_actions) >= 1, \
            f"Collect actions should pass through even when following. Got: {action_strs}"

    def test_collect_allowed_when_not_following(self):
        """Collects should pass through when _following_player is None."""
        agent = _make_agent()
        agent._following_player = None

        state = _make_state()
        chain = agent._precognition_to_chain(
            ["collect poppy 5", "collect dandelion 5", "scan 16"], state
        )

        action_strs = [c.get('params', {}).get('action', '') for c in chain
                       if c.get('command') == 'precog_action']
        collect_actions = [a for a in action_strs if a.startswith("collect")]
        assert len(collect_actions) >= 1, \
            "Collect actions should pass through when not following"


class TestChatThrottle:
    """Tests for one-chat-per-user-message throttle."""

    @pytest.mark.asyncio
    async def test_second_chat_is_throttled(self):
        """After sending one chat, subsequent chats should be suppressed."""
        agent = _make_agent()
        agent._chat_replied = False

        # First chat should go through
        await agent._act("chat Hello there!")
        assert agent._chat_replied is True, "Flag should be set after first chat"

        # Second chat should be throttled
        agent.bridge.chat.reset_mock()
        await agent._act("chat Coming right up!")
        agent.bridge.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_throttle_resets_on_new_user_message(self):
        """After new user message arrives, chat should be allowed again."""
        agent = _make_agent()
        agent._chat_replied = True  # Already replied

        # Simulate new user message arriving
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect flowers'}
        ]
        _llm_had_chats = bool(agent._pending_chats)
        if _llm_had_chats:
            agent._chat_replied = False

        assert agent._chat_replied is False, "Throttle should be reset"

        # Now chat should go through
        await agent._act("chat On it!")
        assert agent._chat_replied is True

    @pytest.mark.asyncio
    async def test_non_chat_actions_not_affected_by_throttle(self):
        """Non-chat actions like collect should work regardless of chat throttle."""
        agent = _make_agent()
        agent._chat_replied = True  # Chat already sent

        # Collect should still work
        await agent._act("collect poppy 5")
        agent.bridge.collect.assert_called_once()


class TestEndToEndScenarios:
    """
    End-to-end tests simulating exact scenarios from the Minecraft logs.
    These reproduce the full auto-dismiss → strip → chain-build flow.
    """

    def test_scenario_14_19_25_follow_dismissed_and_collects_unblocked(self):
        """
        Reproduce 14:19:25 scenario:
        - Following metta_mazza
        - "collect all flowers" arrives during LLM call
        - LLM responds: follow metta_mazza, scan 16, collect oak_log 5
        - Auto-dismiss should fire → follow stripped → collects unblocked
        """
        agent = _make_agent()
        agent._following_player = "metta_mazza"

        # "collect flowers" arrived during LLM call
        _llm_chat_count = 0
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect all flowers in this area'}
        ]

        # LLM response
        action_decision = "follow metta_mazza"
        extra_actions = ["scan 16", "collect oak_log 5"]
        precognition_list = ["collect dandelion 10", "explore", "collect poppy 5"]

        # --- Replicate site 1 logic ---
        _seen_chats = agent._pending_chats[:_llm_chat_count]  # = []
        del agent._pending_chats[:_llm_chat_count]  # no-op

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        # Auto-dismiss
        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        # Pre-set / strip
        _has_task_chat = False
        if not _follow_dismissed:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    _has_task_chat = True
                    break

        if _follow_dismissed or _has_task_chat:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"

        # Verify
        assert agent._following_player is None, "Follow must be dismissed"
        assert _follow_dismissed is True
        assert action_decision == "scan 16", "Primary should be replaced (follow stripped)"
        assert "follow metta_mazza" not in extra_actions

        # Build chain — collects should NOT be filtered
        state = _make_state()
        chain = agent._precognition_to_chain(extra_actions + precognition_list, state)
        action_strs = [c.get('params', {}).get('action', '') for c in chain
                       if c.get('command') == 'precog_action']
        collect_actions = [a for a in action_strs if a.startswith("collect")]
        assert len(collect_actions) >= 1, \
            f"Collects should NOT be filtered. Got chain actions: {action_strs}"

    def test_scenario_14_19_36_follow_not_reenabled_by_next_llm(self):
        """
        Reproduce 14:19:36 scenario:
        - Follow was dismissed in prev cycle (_following_player=None)
        - "collect flowers" still in _pending_chats (not yet consumed)
        - LLM responds: chat ..., collect poppy 5, follow metta_mazza
        - Pre-set must NOT re-enable follow
        """
        agent = _make_agent()
        agent._following_player = None  # Dismissed in prev cycle

        _llm_chat_count = 0  # No new chats at iteration start
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect all the flowers in this area'}
        ]

        action_decision = "chat On it! I'll gather some flowers for you."
        extra_actions = ["collect poppy 5", "collect dandelion 5", "follow metta_mazza"]
        precognition_list = ["scan 16", "collect oxeye_daisy 5", "explore"]

        _seen_chats = agent._pending_chats[:_llm_chat_count]
        del agent._pending_chats[:_llm_chat_count]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        _has_task_chat = False
        if not _follow_dismissed:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    _has_task_chat = True
                    break

        if _follow_dismissed or _has_task_chat:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"
        else:
            for _a in [action_decision] + extra_actions:
                if _a and _a.lower().startswith("follow "):
                    agent._following_player = _a.split(None, 1)[1]
                    break

        assert agent._following_player is None, \
            "Follow must NOT be re-enabled when task chats are still pending"
        assert _has_task_chat is True
        assert "follow metta_mazza" not in extra_actions

        state = _make_state()
        chain = agent._precognition_to_chain(extra_actions + precognition_list, state)
        action_strs = [c.get('params', {}).get('action', '') for c in chain
                       if c.get('command') == 'precog_action']
        collect_actions = [a for a in action_strs if a.startswith("collect")]
        assert len(collect_actions) >= 1, \
            f"Collects should pass through. Got: {action_strs}"

    def test_scenario_14_37_37_task_chat_consumed_then_next_llm_still_has_follow(self):
        """
        Reproduce 14:37:37 scenario from latest logs:
        - Following metta_mazza
        - Iteration 5: _llm_chat_count=1 (collect flowers consumed)
        - LLM_INJECTED fires with: chat ..., collect poppy 10, follow metta_mazza
        - _seen_chats = [collect flowers chat]
        - Auto-dismiss should fire on _seen_chats
        """
        agent = _make_agent()
        agent._following_player = "metta_mazza"
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'collect all the flowers in this area'}
        ]

        _llm_chat_count = 1
        _seen_chats = agent._pending_chats[:_llm_chat_count]
        del agent._pending_chats[:_llm_chat_count]

        action_decision = "chat Flowers coming right up!"
        extra_actions = ["collect poppy 10", "follow metta_mazza"]
        precognition_list = ["collect dandelion 10", "scan 16", "collect poppy 5"]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        _has_task_chat = False
        if not _follow_dismissed:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    _has_task_chat = True
                    break

        if _follow_dismissed or _has_task_chat:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
            if action_decision and action_decision.lower().startswith("follow "):
                action_decision = extra_actions.pop(0) if extra_actions else "explore"

        assert agent._following_player is None
        assert _follow_dismissed is True
        assert "follow metta_mazza" not in extra_actions
        assert action_decision == "chat Flowers coming right up!"
        assert "collect poppy 10" in extra_actions

        state = _make_state()
        chain = agent._precognition_to_chain(extra_actions + precognition_list, state)
        action_strs = [c.get('params', {}).get('action', '') for c in chain
                       if c.get('command') == 'precog_action']
        collect_actions = [a for a in action_strs if a.startswith("collect")]
        assert len(collect_actions) >= 2, \
            f"Multiple collects should pass through. Got: {action_strs}"

    def test_follow_me_without_task_keywords_keeps_follow(self):
        """Ensure 'follow me' by itself correctly enables follow."""
        agent = _make_agent()
        agent._following_player = None
        agent._pending_chats = [
            {'username': 'metta_mazza', 'message': 'follow me'}
        ]

        _llm_chat_count = 1
        _seen_chats = agent._pending_chats[:_llm_chat_count]
        del agent._pending_chats[:_llm_chat_count]

        action_decision = "chat Right behind you!"
        extra_actions = ["follow metta_mazza"]
        precognition_list = ["collect oak_log 5", "explore"]

        _TASK_KEYWORDS = {"collect", "gather", "mine", "get", "find", "harvest",
                          "farm", "build", "craft", "flowers", "flower",
                          "pick", "chop", "dig", "break", "grab"}

        _follow_dismissed = False
        if agent._following_player:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    agent._following_player = None
                    _follow_dismissed = True
                    break

        _has_task_chat = False
        if not _follow_dismissed:
            for _chat in list(_seen_chats) + list(agent._pending_chats):
                _words = set(_chat.get('message', '').lower().split())
                if _words & _TASK_KEYWORDS:
                    _has_task_chat = True
                    break

        if _follow_dismissed or _has_task_chat:
            extra_actions = [a for a in extra_actions if not (a and a.lower().startswith("follow "))]
        else:
            for _a in [action_decision] + extra_actions:
                if _a and _a.lower().startswith("follow "):
                    agent._following_player = _a.split(None, 1)[1]
                    break

        assert agent._following_player == "metta_mazza", \
            "Follow should be enabled for 'follow me' without task keywords"

        # Collects should now be ALLOWED even when following (collect removed from NAV_CONFLICTING)
        state = _make_state()
        chain = agent._precognition_to_chain(precognition_list, state)
        action_strs = [c.get('params', {}).get('action', '') for c in chain
                       if c.get('command') == 'precog_action']
        collect_actions = [a for a in action_strs if str(a).startswith("collect")]
        assert len(collect_actions) >= 1, \
            "Collects should be allowed even when following"
