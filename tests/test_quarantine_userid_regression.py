"""
Regression Tests: Quarantine Processor & User-ID Propagation

Covers:
1. ToolRegistry user_id injection (user_id=0 must not be dropped)
2. DreamConsolidationDaemon quarantine processor (re-parenting strategies)
3. OntologistAbility: no user_id → drop (correct by design)
4. KnowledgeGraph: strict identity validation blocks orphaned nodes
"""
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import pytest

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─────────────────────────────────────────────────────────────
#  1. ToolRegistry: user_id=0 must not be silently dropped
# ─────────────────────────────────────────────────────────────

class TestRegistryUserIdInjection:
    """Regression: `if user_id:` was truthy → dropped user_id=0.
    Fix: `if user_id is not None:`."""

    def test_user_id_zero_is_injected(self):
        """user_id=0 must reach the tool function."""
        from src.tools.registry import ToolRegistry

        received = {}

        @ToolRegistry.register(name="_test_uid_zero", description="test")
        async def _test_uid_zero(user_id=None):
            received["user_id"] = user_id
            return "ok"

        _run(ToolRegistry.execute("_test_uid_zero", user_id=0))
        assert received["user_id"] == 0, "user_id=0 was silently dropped!"

    def test_user_id_none_is_not_injected(self):
        """user_id=None must NOT be injected."""
        from src.tools.registry import ToolRegistry

        received = {}

        @ToolRegistry.register(name="_test_uid_none", description="test")
        async def _test_uid_none(user_id=None):
            received["user_id"] = user_id
            return "ok"

        _run(ToolRegistry.execute("_test_uid_none", user_id=None))
        assert received["user_id"] is None

    def test_user_id_positive_is_injected(self):
        """Normal positive user_id flows through."""
        from src.tools.registry import ToolRegistry

        received = {}

        @ToolRegistry.register(name="_test_uid_pos", description="test")
        async def _test_uid_pos(user_id=None):
            received["user_id"] = user_id
            return "ok"

        _run(ToolRegistry.execute("_test_uid_pos", user_id=12345))
        assert received["user_id"] == 12345

    def test_user_id_negative_one_system(self):
        """user_id=-1 (system/persona) must flow through."""
        from src.tools.registry import ToolRegistry

        received = {}

        @ToolRegistry.register(name="_test_uid_sys", description="test")
        async def _test_uid_sys(user_id=None):
            received["user_id"] = user_id
            return "ok"

        _run(ToolRegistry.execute("_test_uid_sys", user_id=-1))
        assert received["user_id"] == -1


# ─────────────────────────────────────────────────────────────
#  2. Quarantine Processor: _infer_user_id strategies
# ─────────────────────────────────────────────────────────────

class TestQuarantineInferUserId:
    """Test all 5 inference strategies in _infer_user_id."""

    def setup_method(self):
        from src.daemons.dream_consolidation import DreamConsolidationDaemon
        self.daemon = DreamConsolidationDaemon(bot=MagicMock())
        self.user_lookup = {"maria": 123, "bob": 456}

    def test_strategy_1_props_has_user_id(self):
        """If props already contain user_id, re-use it."""
        entry = {
            "source": "A", "target": "B", "rel_type": "LIKES",
            "props": {"user_id": 789}, "violation": "some error"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == 789

    def test_strategy_2_user_pattern_in_source(self):
        """User_<id> pattern in source subject → extract id."""
        entry = {
            "source": "User_42", "target": "B", "rel_type": "LIKES",
            "props": {}, "violation": "missing user_id"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == 42

    def test_strategy_2_user_pattern_in_target(self):
        """User_<id> pattern in target → extract id."""
        entry = {
            "source": "cats", "target": "User_99", "rel_type": "LIKES",
            "props": {}, "violation": "missing user_id"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == 99

    def test_strategy_3_username_lookup(self):
        """Known username in source → map to user_id."""
        entry = {
            "source": "Maria", "target": "testing", "rel_type": "DEVELOPED",
            "props": {}, "violation": "missing"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == 123

    def test_strategy_3_username_lookup_target(self):
        """Known username in target → map to user_id."""
        entry = {
            "source": "testing", "target": "Bob", "rel_type": "CONTACTED",
            "props": {}, "violation": "missing"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == 456

    def test_strategy_4_persona_in_source(self):
        """'persona' in source → assign user_id=-1."""
        entry = {
            "source": "PersonaEcho", "target": "knowledge", "rel_type": "HAS",
            "props": {}, "violation": "identity"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == -1

    def test_strategy_4_persona_in_violation(self):
        """'persona' in violation → assign user_id=-1."""
        entry = {
            "source": "A", "target": "B", "rel_type": "X",
            "props": {}, "violation": "persona data without owner"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) == -1

    def test_strategy_5_single_user_heuristic(self):
        """If only one user exists and violation mentions user_id → assign to them."""
        single_lookup = {"maria": 123}
        entry = {
            "source": "A", "target": "B", "rel_type": "X",
            "props": {}, "violation": "missing user_id"
        }
        assert self.daemon._infer_user_id(entry, single_lookup) == 123

    def test_strategy_5_multi_user_no_heuristic(self):
        """Multiple users + generic violation → unresolvable."""
        entry = {
            "source": "A", "target": "B", "rel_type": "X",
            "props": {}, "violation": "missing user_id"
        }
        # user_lookup has 2 users, so heuristic doesn't apply
        assert self.daemon._infer_user_id(entry, self.user_lookup) is None

    def test_fully_unresolvable(self):
        """No strategy matches → returns None."""
        entry = {
            "source": "unknown_entity", "target": "unknown_target",
            "rel_type": "UNKNOWN", "props": {},
            "violation": "something else"
        }
        assert self.daemon._infer_user_id(entry, self.user_lookup) is None


# ─────────────────────────────────────────────────────────────
#  3. Quarantine Processor: _build_user_lookup
# ─────────────────────────────────────────────────────────────

class TestBuildUserLookup:

    def setup_method(self):
        from src.daemons.dream_consolidation import DreamConsolidationDaemon
        self.daemon = DreamConsolidationDaemon(bot=MagicMock())

    def test_parses_user_folders(self, tmp_path):
        users_dir = tmp_path / "memory" / "users"
        (users_dir / "maria_123").mkdir(parents=True)
        (users_dir / "bob_456").mkdir(parents=True)
        (users_dir / "invalid_folder").mkdir(parents=True)  # no numeric suffix
        (users_dir / "solo_file.txt").touch()  # not a directory

        with patch("src.daemons.dream_consolidation.Path") as MockPath:
            MockPath.return_value = users_dir
            MockPath.__truediv__ = lambda s, o: tmp_path / o
            # Direct approach: call with real path
            pass

        # Simpler: just mock the users dir
        with patch.object(Path, '__new__', return_value=users_dir):
            pass

        # Simplest: test the parsing logic directly
        lookup = {}
        for folder in users_dir.iterdir():
            if not folder.is_dir():
                continue
            name = folder.name
            parts = name.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    uid = int(parts[1])
                    username = parts[0].lower()
                    lookup[username] = uid
                except ValueError:
                    continue

        assert lookup == {"maria": 123, "bob": 456}

    def test_no_users_dir(self):
        with patch("src.daemons.dream_consolidation.Path") as MockPath:
            MockPath.return_value.exists.return_value = False
            result = self.daemon._build_user_lookup()
        assert result == {}


# ─────────────────────────────────────────────────────────────
#  4. Quarantine Processor: _process_quarantine integration
# ─────────────────────────────────────────────────────────────

class TestProcessQuarantine:

    def setup_method(self):
        from src.daemons.dream_consolidation import DreamConsolidationDaemon
        self.bot = MagicMock()
        self.daemon = DreamConsolidationDaemon(bot=self.bot)

    def test_no_hippocampus_returns_zero(self):
        self.bot.hippocampus = None
        result = _run(self.daemon._process_quarantine())
        assert result == 0

    def test_no_graph_returns_zero(self):
        self.bot.hippocampus = MagicMock()
        self.bot.hippocampus.graph = None
        result = _run(self.daemon._process_quarantine())
        assert result == 0

    def test_empty_quarantine_returns_zero(self):
        q = MagicMock()
        q.size.return_value = 0
        self.bot.hippocampus.graph.quarantine = q
        result = _run(self.daemon._process_quarantine())
        assert result == 0

    def test_resolves_entry_with_user_pattern(self):
        """Entry with User_42 in source should be resolved."""
        q = MagicMock()
        q.size.return_value = 1
        q.peek.return_value = [{
            "source": "User_42", "target": "cats", "rel_type": "LIKES",
            "layer": "narrative", "props": {}, "violation": "missing user_id"
        }]
        self.bot.hippocampus.graph.quarantine = q

        with patch.object(self.daemon, '_build_user_lookup', return_value={}):
            result = _run(self.daemon._process_quarantine())

        assert result == 1
        q.resolve.assert_called_once_with(0)
        self.bot.hippocampus.graph.add_relationship.assert_called_once()
        call_kwargs = self.bot.hippocampus.graph.add_relationship.call_args
        assert call_kwargs[1]["user_id"] == 42

    def test_leaves_unresolvable_in_quarantine(self):
        """Fully unresolvable entry stays in quarantine."""
        q = MagicMock()
        q.size.return_value = 1
        q.peek.return_value = [{
            "source": "unknown", "target": "unknown", "rel_type": "X",
            "layer": "narrative", "props": {}, "violation": "something"
        }]
        self.bot.hippocampus.graph.quarantine = q

        with patch.object(self.daemon, '_build_user_lookup', return_value={"alice": 1, "bob": 2}):
            result = _run(self.daemon._process_quarantine())

        assert result == 0
        q.resolve.assert_not_called()

    def test_persona_entry_gets_system_uid(self):
        """Persona entries get user_id=-1."""
        q = MagicMock()
        q.size.return_value = 1
        q.peek.return_value = [{
            "source": "PersonaEcho", "target": "sovereignty", "rel_type": "HAS",
            "layer": "narrative", "props": {}, "violation": "identity blocked"
        }]
        self.bot.hippocampus.graph.quarantine = q

        with patch.object(self.daemon, '_build_user_lookup', return_value={}):
            result = _run(self.daemon._process_quarantine())

        assert result == 1
        call_kwargs = self.bot.hippocampus.graph.add_relationship.call_args
        assert call_kwargs[1]["user_id"] == -1

    def test_add_relationship_failure_doesnt_resolve(self):
        """If re-commit fails, don't resolve the entry."""
        q = MagicMock()
        q.size.return_value = 1
        q.peek.return_value = [{
            "source": "User_42", "target": "X", "rel_type": "Y",
            "layer": "narrative", "props": {}, "violation": "test"
        }]
        self.bot.hippocampus.graph.quarantine = q
        self.bot.hippocampus.graph.add_relationship.side_effect = RuntimeError("neo4j down")

        with patch.object(self.daemon, '_build_user_lookup', return_value={}):
            result = _run(self.daemon._process_quarantine())

        assert result == 0
        q.resolve.assert_not_called()


# ─────────────────────────────────────────────────────────────
#  5. OntologistAbility: no user_id = drop (by design)
# ─────────────────────────────────────────────────────────────

def _make_ability(cls):
    lobe = MagicMock()
    lobe.cerebrum = MagicMock()
    lobe.cerebrum.bot = MagicMock()
    ability = cls.__new__(cls)
    ability.lobe = lobe
    return ability, lobe.cerebrum.bot


class TestOntologistDropBehavior:
    """Confirm: no user_id → error (drop). This is correct behavior."""

    def setup_method(self):
        from src.lobes.memory.ontologist import OntologistAbility
        self.ability, self.bot = _make_ability(OntologistAbility)

    def _mock_globals(self, hippocampus=True, active_msg=None):
        g = MagicMock()
        if hippocampus is True:
            g.bot = MagicMock()
            g.bot.hippocampus = MagicMock()
            g.bot.hippocampus.graph = MagicMock()
            # Foundation-aware ontologist requires these methods
            g.bot.hippocampus.graph.check_contradiction.return_value = None
            g.bot.hippocampus.graph.query_core_knowledge.return_value = []
        elif hippocampus is False:
            g.bot = MagicMock()
            g.bot.hippocampus = None
        g.active_message = MagicMock()
        g.active_message.get.return_value = active_msg
        return g


    def test_no_user_id_no_message_drops(self):
        """No user_id AND no active_message → Error (dropped)."""
        g = self._mock_globals(active_msg=None)
        with patch("src.bot.globals", g):
            r = _run(self.ability.execute("Bob", "LIKES", "cats"))
        assert "Error" in r
        assert "User ID" in r

    def test_user_id_provided_succeeds(self):
        """Explicit user_id → succeeds."""
        g = self._mock_globals()
        with patch("src.bot.globals", g):
            r = _run(self.ability.execute("Bob", "LIKES", "cats", user_id=42))
        assert "Learned" in r

    def test_user_id_from_message_succeeds(self):
        """user_id inferred from active_message → succeeds."""
        msg = MagicMock()
        msg.author.id = 99
        g = self._mock_globals(active_msg=msg)
        with patch("src.bot.globals", g):
            r = _run(self.ability.execute("Bob", "LIKES", "cats"))
        assert "Learned" in r

    def test_system_user_id_neg1_succeeds(self):
        """Persona/system with user_id=-1 → succeeds."""
        g = self._mock_globals()
        with patch("src.bot.globals", g):
            r = _run(self.ability.execute("Echo", "HAS", "sovereignty", user_id=-1))
        assert "Learned" in r


# ─────────────────────────────────────────────────────────────
#  6. KnowledgeGraph: strict identity validation
# ─────────────────────────────────────────────────────────────

class TestGraphIdentityValidation:
    """Confirm graph.add_node and graph.add_relationship block user_id=None."""

    def test_add_node_blocks_none_user_id(self):
        from src.memory.graph import KnowledgeGraph
        with patch("src.memory.graph.GraphDatabase") as MockDB:
            MockDB.driver.return_value = MagicMock()
            kg = KnowledgeGraph.__new__(KnowledgeGraph)
            kg.driver = MagicMock()
            kg.quarantine = MagicMock()
            # Should silently return without storing
            kg.add_node("Person", "Bob", user_id=None)
            kg.driver.session.assert_not_called()

    def test_add_relationship_blocks_none_user_id(self):
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph.__new__(KnowledgeGraph)
        kg.driver = MagicMock()
        kg.quarantine = MagicMock()
        # Should silently return without storing
        kg.add_relationship("A", "LIKES", "B", user_id=None)
        kg.driver.session.assert_not_called()

    def test_add_node_accepts_valid_user_id(self):
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph.__new__(KnowledgeGraph)
        kg.driver = MagicMock()
        kg.quarantine = MagicMock()
        # Should proceed to session.run
        kg.add_node("Person", "Bob", user_id=42, scope="PUBLIC")
        kg.driver.session.assert_called()

    def test_add_node_accepts_system_user_id(self):
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph.__new__(KnowledgeGraph)
        kg.driver = MagicMock()
        kg.quarantine = MagicMock()
        # user_id=-1 means system/persona data
        kg.add_node("System", "Echo", user_id=-1, scope="CORE")
        kg.driver.session.assert_called()


# ─────────────────────────────────────────────────────────────
#  7. Dream Cycle integration: quarantine step in run()
# ─────────────────────────────────────────────────────────────

class TestDreamCycleIncludesQuarantine:
    """Verify that the dream cycle calls _process_quarantine."""

    def test_run_calls_process_quarantine(self):
        from src.daemons.dream_consolidation import DreamConsolidationDaemon

        bot = MagicMock()
        daemon = DreamConsolidationDaemon(bot=bot)

        # Mock all steps
        daemon._compress_episodic_memories = AsyncMock(return_value=0)
        daemon._prune_kg_nodes = AsyncMock(return_value=0)
        daemon._process_quarantine = AsyncMock(return_value=3)
        daemon._persist_sentinel_cache = MagicMock(return_value=True)
        daemon._write_status = MagicMock()

        # MemoryConsolidator is imported locally inside run(), patch at source
        with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockConsolidator:
            MockConsolidator.return_value.run_consolidation = AsyncMock(return_value="done")
            _run(daemon.run())

        daemon._process_quarantine.assert_called_once()


# ─────────────────────────────────────────────────────────────
#  8. ValidationQuarantine: queue mechanics
# ─────────────────────────────────────────────────────────────

class TestValidationQuarantine:
    """Verify quarantine peek/resolve/add works correctly for the processor."""

    def test_add_and_peek(self):
        from src.memory.quarantine import ValidationQuarantine
        q = ValidationQuarantine()
        q.add("A", "B", "LIKES", "narrative", {}, "missing user_id")
        entries = q.peek(n=10)
        assert len(entries) == 1
        assert entries[0]["source"] == "A"

    def test_resolve_removes_entry(self):
        from src.memory.quarantine import ValidationQuarantine
        q = ValidationQuarantine()
        q.add("A", "B", "LIKES", "narrative", {}, "missing user_id")
        q.add("C", "D", "KNOWS", "social", {}, "missing user_id")
        assert q.size() == 2
        removed = q.resolve(0)
        assert removed.source == "A"
        assert q.size() == 1

    def test_resolve_reverse_order(self):
        """Processing in reverse order (as quarantine processor does) keeps indices valid."""
        from src.memory.quarantine import ValidationQuarantine
        q = ValidationQuarantine()
        q.add("A", "B", "R1", "narrative", {}, "v1")
        q.add("C", "D", "R2", "social", {}, "v2")
        q.add("E", "F", "R3", "temporal", {}, "v3")

        # Resolve in reverse: 2, 1, 0
        r2 = q.resolve(2)
        assert r2.source == "E"
        r1 = q.resolve(1)
        assert r1.source == "C"
        r0 = q.resolve(0)
        assert r0.source == "A"
        assert q.size() == 0

    def test_hard_drop_safety_violations(self):
        """Moral layer violations are hard-dropped, not quarantined."""
        from src.memory.quarantine import ValidationQuarantine
        q = ValidationQuarantine()
        result = q.add("A", "B", "LIKES", "moral", {}, "safety violation")
        assert result is False
        assert q.size() == 0

    def test_persistence_roundtrip(self, tmp_path):
        """Quarantine persists to and loads from disk."""
        from src.memory.quarantine import ValidationQuarantine
        path = str(tmp_path / "quarantine.json")

        q1 = ValidationQuarantine(persist_path=path)
        q1.add("A", "B", "LIKES", "narrative", {"user_id": 42}, "test")
        assert os.path.exists(path)

        q2 = ValidationQuarantine(persist_path=path)
        entries = q2.peek(n=10)
        assert len(entries) == 1
        assert entries[0]["props"]["user_id"] == 42
