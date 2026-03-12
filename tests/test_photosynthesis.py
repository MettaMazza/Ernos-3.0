"""
Tests for v3.5 Photosynthesis: Skill Forge, Prompt Tuner,
Test Forge, and Introspection Engine.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


# ──────────────────────────────────────────────────────────────
# Skill Forge Tests
# ──────────────────────────────────────────────────────────────

class TestSkillForge:
    """Tests for self-authored skills."""

    def test_propose_skill(self, tmp_path):
        from src.lobes.strategy.skill_forge import SkillForge
        with patch.object(SkillForge, 'FORGE_DIR', tmp_path / "forge"), \
             patch.object(SkillForge, 'QUEUE_FILE', tmp_path / "forge/pending.json"), \
             patch.object(SkillForge, 'LOG_FILE', tmp_path / "forge/log.json"), \
             patch("src.lobes.strategy.skill_forge._PROJECT_ROOT", tmp_path):
            
            forge = SkillForge()
            proposal = forge.propose_skill(
                name="greet_user",
                description="Greet a user warmly",
                instructions="When user says hello, run this code.",
                allowed_tools=[],
                user_id="test_user",
                scope="PRIVATE"
            )
            
            assert proposal["status"] == "active"
            assert proposal["name"] == "greet_user"
            # It's not pending anymore
            # assert len(forge.get_pending()) == 1







# ──────────────────────────────────────────────────────────────
# Prompt Tuner Tests
# ──────────────────────────────────────────────────────────────

class TestPromptTuner:
    """Tests for self-tuning prompts."""

    def test_propose_modification(self, tmp_path):
        from src.lobes.strategy.prompt_tuner import PromptTuner
        with patch.object(PromptTuner, 'TUNER_DIR', tmp_path / "tuner"), \
             patch.object(PromptTuner, 'PROPOSALS_FILE', tmp_path / "tuner/proposals.json"), \
             patch.object(PromptTuner, 'HISTORY_FILE', tmp_path / "tuner/history.json"):
            
            tuner = PromptTuner()
            proposal = tuner.propose_modification(
                prompt_file="src/prompts/kernel.md",
                section="greeting",
                current_text="Hello",
                proposed_text="Hey there!",
                rationale="More casual tone"
            )
            
            assert proposal["status"] == "pending"
            assert len(proposal["id"]) == 12

    def test_reject_modification(self, tmp_path):
        from src.lobes.strategy.prompt_tuner import PromptTuner
        with patch.object(PromptTuner, 'TUNER_DIR', tmp_path / "tuner"), \
             patch.object(PromptTuner, 'PROPOSALS_FILE', tmp_path / "tuner/proposals.json"), \
             patch.object(PromptTuner, 'HISTORY_FILE', tmp_path / "tuner/history.json"):
            
            tuner = PromptTuner()
            proposal = tuner.propose_modification("file", "s", "old", "new", "r")
            result = tuner.reject_modification(proposal["id"], "not needed")
            assert result is True
            assert len(tuner.get_pending()) == 0

    def test_approve_with_backup(self, tmp_path):
        from src.lobes.strategy.prompt_tuner import PromptTuner
        
        # Create a mock prompt file
        prompt_file = tmp_path / "test_prompt.md"
        prompt_file.write_text("Hello world, be nice.")
        
        with patch.object(PromptTuner, 'TUNER_DIR', tmp_path / "tuner"), \
             patch.object(PromptTuner, 'PROPOSALS_FILE', tmp_path / "tuner/proposals.json"), \
             patch.object(PromptTuner, 'HISTORY_FILE', tmp_path / "tuner/history.json"):
            
            tuner = PromptTuner()
            proposal = tuner.propose_modification(
                str(prompt_file), "greeting",
                "Hello world", "Hey there",
                "More casual"
            )
            result = tuner.approve_modification(proposal["id"], "admin")
            assert result is True
            
            # File should be modified
            assert "Hey there" in prompt_file.read_text()
            
            # Backup should exist
            backup_dir = tmp_path / "tuner" / "backups"
            assert backup_dir.exists()

    def test_tuner_summary(self, tmp_path):
        from src.lobes.strategy.prompt_tuner import PromptTuner
        with patch.object(PromptTuner, 'TUNER_DIR', tmp_path / "tuner"), \
             patch.object(PromptTuner, 'PROPOSALS_FILE', tmp_path / "tuner/proposals.json"), \
             patch.object(PromptTuner, 'HISTORY_FILE', tmp_path / "tuner/history.json"):
            
            tuner = PromptTuner()
            summary = tuner.get_tuner_summary()
            assert "0 pending" in summary


# ──────────────────────────────────────────────────────────────
# Test Forge Tests
# ──────────────────────────────────────────────────────────────

class TestTestForge:
    """Tests for self-generating tests."""

    def test_propose_test(self, tmp_path):
        from src.lobes.strategy.test_forge import TestForge
        with patch.object(TestForge, 'STAGING_DIR', tmp_path / "staging"), \
             patch.object(TestForge, 'LOG_FILE', tmp_path / "log.json"):
            
            forge = TestForge()
            proposal = forge.propose_test(
                "my_feature",
                "src.my_module",
                "def test_it(): assert True",
                "Need coverage"
            )
            
            assert proposal["name"] == "test_my_feature"
            assert (tmp_path / "staging" / "test_my_feature.py").exists()

    def test_reject_test(self, tmp_path):
        from src.lobes.strategy.test_forge import TestForge
        with patch.object(TestForge, 'STAGING_DIR', tmp_path / "staging"), \
             patch.object(TestForge, 'LOG_FILE', tmp_path / "log.json"):
            
            forge = TestForge()
            forge.propose_test("bad", "mod", "code", "r")
            result = forge.reject_test("test_bad", "not needed")
            assert result is True

    def test_forge_summary(self, tmp_path):
        from src.lobes.strategy.test_forge import TestForge
        with patch.object(TestForge, 'STAGING_DIR', tmp_path / "staging"), \
             patch.object(TestForge, 'LOG_FILE', tmp_path / "log.json"):
            
            forge = TestForge()
            summary = forge.get_forge_summary()
            assert "0 staged" in summary


# ──────────────────────────────────────────────────────────────
# Introspection Engine Tests
# ──────────────────────────────────────────────────────────────

class TestIntrospection:
    """Tests for self-reflective analysis."""

    def test_record_lobe_call(self, tmp_path):
        from src.lobes.strategy.introspection import IntrospectionEngine
        with patch.object(IntrospectionEngine, 'REPORT_DIR', tmp_path / "intro"), \
             patch.object(IntrospectionEngine, 'METRICS_FILE', tmp_path / "intro/metrics.json"):
            
            engine = IntrospectionEngine()
            engine.record_lobe_call("Cerebrum", 150.0)
            engine.record_lobe_call("Cerebrum", 200.0)
            
            assert engine._metrics["lobe_calls"]["Cerebrum"]["count"] == 2
            assert engine._metrics["lobe_calls"]["Cerebrum"]["total_ms"] == 350.0

    def test_response_time_tracking(self, tmp_path):
        from src.lobes.strategy.introspection import IntrospectionEngine
        with patch.object(IntrospectionEngine, 'REPORT_DIR', tmp_path / "intro"), \
             patch.object(IntrospectionEngine, 'METRICS_FILE', tmp_path / "intro/metrics.json"):
            
            engine = IntrospectionEngine()
            engine.record_response_time(500.0, "test")
            engine.record_response_time(300.0, "test2")
            
            assert len(engine._metrics["response_times"]) == 2

    def test_error_tracking(self, tmp_path):
        from src.lobes.strategy.introspection import IntrospectionEngine
        with patch.object(IntrospectionEngine, 'REPORT_DIR', tmp_path / "intro"), \
             patch.object(IntrospectionEngine, 'METRICS_FILE', tmp_path / "intro/metrics.json"):
            
            engine = IntrospectionEngine()
            engine.record_error("Cerebrum", "TimeoutError")
            engine.record_error("Cerebrum", "TimeoutError")
            
            assert engine._metrics["error_counts"]["Cerebrum:TimeoutError"] == 2

    def test_health_report(self, tmp_path):
        from src.lobes.strategy.introspection import IntrospectionEngine
        with patch.object(IntrospectionEngine, 'REPORT_DIR', tmp_path / "intro"), \
             patch.object(IntrospectionEngine, 'METRICS_FILE', tmp_path / "intro/metrics.json"):
            
            engine = IntrospectionEngine()
            engine.record_lobe_call("Cerebrum", 100.0)
            engine.record_response_time(500.0)
            
            report = engine.get_health_report()
            assert "System Health Report" in report
            assert "Cerebrum" in report

    def test_bottleneck_detection(self, tmp_path):
        from src.lobes.strategy.introspection import IntrospectionEngine
        with patch.object(IntrospectionEngine, 'REPORT_DIR', tmp_path / "intro"), \
             patch.object(IntrospectionEngine, 'METRICS_FILE', tmp_path / "intro/metrics.json"):
            
            engine = IntrospectionEngine()
            # Simulate slow lobe
            engine._metrics["lobe_calls"]["SlowLobe"] = {"count": 10, "total_ms": 60000}
            # Simulate error-prone component
            engine._metrics["error_counts"]["BuggyModule:ValueError"] = 15
            
            issues = engine.identify_bottlenecks()
            assert len(issues) >= 2

    def test_summary(self, tmp_path):
        from src.lobes.strategy.introspection import IntrospectionEngine
        with patch.object(IntrospectionEngine, 'REPORT_DIR', tmp_path / "intro"), \
             patch.object(IntrospectionEngine, 'METRICS_FILE', tmp_path / "intro/metrics.json"):
            
            engine = IntrospectionEngine()
            summary = engine.get_summary()
            assert "Introspection" in summary
