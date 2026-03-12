"""
Tests for v3.3 Mycelium Network: Social Graph, Group Dynamics,
Conflict Detection, and Proactive Relationship Care.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ──────────────────────────────────────────────────────────────
# Social Graph Tests
# ──────────────────────────────────────────────────────────────

class TestSocialGraph:
    """Tests for user connection tracking."""

    def test_record_mention(self, tmp_path):
        from src.memory.social_graph import SocialGraphManager
        with patch.object(SocialGraphManager, 'GRAPH_FILE', tmp_path / "graph.json"):
            sg = SocialGraphManager()
            sg.record_mention(100, 200, channel_id=999, context="talking about Bob")
            
            assert "100" in sg._local_graph["nodes"]
            assert "200" in sg._local_graph["nodes"]
            assert len(sg._local_graph["edges"]) == 1
            assert sg._local_graph["edges"][0]["from"] == 100

    def test_get_connections(self, tmp_path):
        from src.memory.social_graph import SocialGraphManager
        with patch.object(SocialGraphManager, 'GRAPH_FILE', tmp_path / "graph.json"):
            sg = SocialGraphManager()
            sg.record_mention(100, 200, 999)
            sg.record_mention(100, 200, 999)
            sg.record_mention(100, 300, 999)
            
            connections = sg.get_connections(100)
            assert len(connections) == 2
            # User 200 mentioned twice, should be first
            assert connections[0]["user_id"] == 200
            assert connections[0]["mention_count"] == 2

    def test_co_occurrence(self, tmp_path):
        from src.memory.social_graph import SocialGraphManager
        with patch.object(SocialGraphManager, 'GRAPH_FILE', tmp_path / "graph.json"):
            sg = SocialGraphManager()
            sg.record_co_occurrence([100, 200, 300], channel_id=999)
            
            assert "999" in sg._local_graph["groups"]
            assert 100 in sg._local_graph["groups"]["999"]["members"]
            assert 300 in sg._local_graph["groups"]["999"]["members"]

    def test_shared_groups(self, tmp_path):
        from src.memory.social_graph import SocialGraphManager
        with patch.object(SocialGraphManager, 'GRAPH_FILE', tmp_path / "graph.json"):
            sg = SocialGraphManager()
            sg.record_co_occurrence([100, 200], channel_id=111)
            sg.record_co_occurrence([100, 300], channel_id=222)
            sg.record_co_occurrence([200, 300], channel_id=333)
            
            shared = sg.get_shared_groups(100, 200)
            assert 111 in shared

    def test_graph_summary(self, tmp_path):
        from src.memory.social_graph import SocialGraphManager
        with patch.object(SocialGraphManager, 'GRAPH_FILE', tmp_path / "graph.json"):
            sg = SocialGraphManager()
            sg.record_mention(100, 200, 999)
            summary = sg.get_graph_summary()
            assert "2 users" in summary
            assert "1 connections" in summary


# ──────────────────────────────────────────────────────────────
# Group Dynamics Tests
# ──────────────────────────────────────────────────────────────

class TestGroupDynamics:
    """Tests for conversation dynamics tracking."""

    def test_record_message(self, tmp_path):
        from src.lobes.interaction.group_dynamics import GroupDynamicsEngine
        with patch.object(GroupDynamicsEngine, 'DYNAMICS_DIR', tmp_path / "dynamics"):
            gd = GroupDynamicsEngine()
            gd.record_message(999, 100, message_length=50)
            gd.record_message(999, 100, message_length=100)
            gd.record_message(999, 200, message_length=30)
            
            assert gd._channel_data["999"]["total_messages"] == 3

    def test_dominant_speaker(self, tmp_path):
        from src.lobes.interaction.group_dynamics import GroupDynamicsEngine
        with patch.object(GroupDynamicsEngine, 'DYNAMICS_DIR', tmp_path / "dynamics"):
            gd = GroupDynamicsEngine()
            for _ in range(10):
                gd.record_message(999, 100, 50)
            for _ in range(3):
                gd.record_message(999, 200, 50)
            
            dominant = gd.get_dominant_speaker(999)
            assert dominant == 100

    def test_quiet_users(self, tmp_path):
        from src.lobes.interaction.group_dynamics import GroupDynamicsEngine
        with patch.object(GroupDynamicsEngine, 'DYNAMICS_DIR', tmp_path / "dynamics"):
            gd = GroupDynamicsEngine()
            for _ in range(20):
                gd.record_message(999, 100, 50)
            gd.record_message(999, 200, 50)
            
            quiet = gd.get_quiet_users(999)
            assert 200 in quiet
            assert 100 not in quiet

    def test_channel_dynamics_balance(self, tmp_path):
        from src.lobes.interaction.group_dynamics import GroupDynamicsEngine
        with patch.object(GroupDynamicsEngine, 'DYNAMICS_DIR', tmp_path / "dynamics"):
            gd = GroupDynamicsEngine()
            # Balanced conversation
            for _ in range(5):
                gd.record_message(999, 100, 50)
                gd.record_message(999, 200, 50)
            
            dynamics = gd.get_channel_dynamics(999)
            assert dynamics["active_users"] == 2
            assert dynamics["balance_ratio"] == 1.0  # Perfectly balanced

    def test_turn_taking_pairs(self, tmp_path):
        from src.lobes.interaction.group_dynamics import GroupDynamicsEngine
        with patch.object(GroupDynamicsEngine, 'DYNAMICS_DIR', tmp_path / "dynamics"):
            gd = GroupDynamicsEngine()
            for _ in range(5):
                gd.record_message(999, 100, 50, reply_to=200)
            gd.record_message(999, 300, 50, reply_to=100)
            
            pairs = gd.get_turn_taking_pairs(999)
            assert len(pairs) >= 1
            assert pairs[0]["exchanges"] == 5


# ──────────────────────────────────────────────────────────────
# Conflict Sensor Tests
# ──────────────────────────────────────────────────────────────

class TestConflictSensor:
    """Tests for conflict detection."""

    def test_clean_message(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        result = cs.analyze_message("Hey, how are you today?", 100, 999)
        assert result["score"] < 0.3
        assert result["recommended_action"] == "normal"

    def test_aggressive_message(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        result = cs.analyze_message("shut up you idiot, you're so stupid", 100, 999)
        assert result["score"] >= 0.5
        assert len(result["signals"]) > 0
        assert result["recommended_action"] in ("de-escalate", "soften_tone")

    def test_frustration_detection(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        result = cs.analyze_message("Why can't you do anything right? I already told you!", 100, 999)
        assert result["score"] > 0.2
        assert any("frustration" in s for s in result["signals"])

    def test_shouting_detection(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        result = cs.analyze_message("STOP DOING THAT RIGHT NOW", 100, 999)
        assert result["score"] > 0
        assert any("shouting" in s for s in result["signals"])

    def test_escalation_detection(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        # Simulate escalating conflict
        cs.analyze_message("this is fine", 100, 999)
        cs.analyze_message("you're wrong about that", 100, 999)
        result = cs.analyze_message("shut up you idiot, hate you!", 100, 999)
        assert result["escalating"] is True

    def test_channel_tension(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        cs.analyze_message("hello", 100, 999)
        cs.analyze_message("shut up idiot", 100, 999)
        tension = cs.get_channel_tension(999)
        assert tension > 0

    def test_alerts_recorded(self):
        from src.lobes.interaction.conflict_sensor import ConflictSensor
        cs = ConflictSensor()
        cs.analyze_message("shut up you stupid idiot moron", 100, 999)
        alerts = cs.get_recent_alerts()
        assert len(alerts) >= 1


# ──────────────────────────────────────────────────────────────
# Relationship Care Tests
# ──────────────────────────────────────────────────────────────

class TestRelationshipCare:
    """Tests for proactive relationship maintenance."""

    @patch("src.privacy.scopes.ScopeManager.get_user_root_home")
    def test_relationship_health(self, mock_home, tmp_path):
        from src.memory.relationships import RelationshipManager
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        mock_home.return_value = user_dir
        
        # Create relationship data
        from src.memory.relationships import RelationshipData
        data = RelationshipData(
            user_id=12345,
            trust=80, respect=70, affinity=60,
            interaction_count=50,
            last_seen=datetime.now().isoformat()
        )
        rel_path = user_dir / "relationship.json"
        from dataclasses import asdict
        rel_path.write_text(json.dumps(asdict(data)))
        
        health = RelationshipManager.get_relationship_health(12345)
        assert 0.0 <= health <= 1.0
        assert health > 0.5  # Good health with high dimensions

    @patch("src.privacy.scopes.ScopeManager.get_user_root_home")
    def test_new_user_default_health(self, mock_home, tmp_path):
        from src.memory.relationships import RelationshipManager
        user_dir = tmp_path / "newuser"
        user_dir.mkdir()
        mock_home.return_value = user_dir
        
        health = RelationshipManager.get_relationship_health(99999)
        assert 0.0 <= health <= 1.0
