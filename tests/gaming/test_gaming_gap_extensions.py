"""
Tests for skill_library.py — Extended Skill dataclass with code + skill_type fields.
These tests supplement the existing test_skill_library.py with coverage for new fields.
"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestSkillCodeField:
    """Tests for code and skill_type fields added to Skill."""

    def test_default_skill_type_is_steps(self):
        """New skills should default to 'steps' type."""
        from src.gaming.skill_library import Skill

        skill = Skill(name="test", description="d", goal="g", steps=["a"])
        assert skill.skill_type == "steps"
        assert skill.code == ""

    def test_code_skill_creation(self):
        """Code-type skills should store JavaScript."""
        from src.gaming.skill_library import Skill

        code = "async function buildHouse(bot) { /* ... */ }"
        skill = Skill(
            name="build_house",
            description="Build a wooden house",
            goal="house",
            steps=[],
            code=code,
            skill_type="code",
        )
        assert skill.skill_type == "code"
        assert "buildHouse" in skill.code

    def test_code_field_serializes(self):
        """Code field should survive to_dict / from_dict round-trip."""
        from src.gaming.skill_library import Skill

        code = "async function test(bot) { return true; }"
        skill = Skill(
            name="test",
            description="test",
            goal="test",
            steps=[],
            code=code,
            skill_type="code",
        )

        d = skill.to_dict()
        assert d["code"] == code
        assert d["skill_type"] == "code"

        # JSON round-trip
        json_str = json.dumps(d)
        restored = Skill.from_dict(json.loads(json_str))
        assert restored.code == code
        assert restored.skill_type == "code"

    def test_code_field_persists(self, tmp_path):
        """Code skills should persist to disk and load correctly."""
        from src.gaming.skill_library import SkillLibrary, Skill

        skills_file = str(tmp_path / "code_skills.json")
        lib = SkillLibrary(skills_file=skills_file)

        # Manually inject a code skill
        skill = Skill(
            name="get_custom",
            description="Custom JS skill",
            goal="custom",
            steps=[],
            code="bot.chat('hello')",
            skill_type="code",
            success_count=1,
        )
        lib.skills["get_custom"] = skill
        lib._save()

        # Reload
        lib2 = SkillLibrary(skills_file=skills_file)
        loaded = lib2.retrieve("custom")
        assert loaded is not None
        assert loaded.code == "bot.chat('hello')"
        assert loaded.skill_type == "code"

    def test_backward_compat_no_code_field(self, tmp_path):
        """Skills saved without code field should load with defaults."""
        from src.gaming.skill_library import SkillLibrary

        skills_file = str(tmp_path / "old_skills.json")
        # Write old-format skill (no code/skill_type)
        old_data = {
            "get_test": {
                "name": "get_test",
                "description": "d",
                "goal": "test",
                "steps": ["a"],
                "success_count": 1,
                "failure_count": 0,
                "avg_duration": 0.0,
                "created_at": "",
                "last_used": "",
            }
        }
        with open(skills_file, "w") as f:
            json.dump(old_data, f)

        # Load should work, defaulting code="" and skill_type="steps"
        lib = SkillLibrary(skills_file=skills_file)
        skill = lib.retrieve("test")
        assert skill is not None
        assert skill.code == ""
        assert skill.skill_type == "steps"

    def test_success_rate_unaffected(self):
        """New fields should not affect success_rate calculation."""
        from src.gaming.skill_library import Skill

        skill = Skill(
            name="test",
            description="d",
            goal="g",
            steps=[],
            code="code",
            skill_type="code",
            success_count=7,
            failure_count=3,
        )
        assert skill.success_rate == 0.7

    def test_record_success_with_code_skill(self, tmp_path):
        """record_success (via store) should work with code skills."""
        from src.gaming.skill_library import SkillLibrary

        lib = SkillLibrary(skills_file=str(tmp_path / "s.json"))
        lib.store("test", ["step1"], duration=10)
        lib.store("test", ["step1"], duration=20)
        skill = lib.retrieve("test")
        assert skill.success_count == 2


class TestPlannerDynamicKnowledge:
    """Tests for planner.py integration with dynamic knowledge_base."""

    def test_dynamic_recipe_lookup(self, monkeypatch):
        """Planner should use dynamic knowledge for unknown items."""
        from src.gaming.planner import HierarchicalPlanner
        from src.gaming import knowledge_base

        # Feed a recipe for an item not in tech_tree
        monkeypatch.setattr(
            knowledge_base,
            "get_knowledge_base",
            lambda: type("KB", (), {
                "lookup_recipe": lambda self, item: {
                    "ingredients": {"oak_log": 4},
                    "source": "test",
                    "needs_table": False,
                } if item == "custom_item" else None
            })(),
        )

        planner = HierarchicalPlanner()
        plan = planner.decompose("custom_item", {}, 1)

        actions = [s.action for s in plan]
        targets = [s.target for s in plan]

        # Should collect oak_log and craft custom_item
        assert "collect" in actions
        assert "oak_log" in targets
        assert "craft" in actions
        assert "custom_item" in targets

    def test_unknown_item_falls_to_collect(self, monkeypatch):
        """Items unknown to both tech tree and knowledge base should be collected."""
        from src.gaming.planner import HierarchicalPlanner
        from src.gaming import knowledge_base

        monkeypatch.setattr(
            knowledge_base,
            "get_knowledge_base",
            lambda: type("KB", (), {
                "lookup_recipe": lambda self, item: None
            })(),
        )

        planner = HierarchicalPlanner()
        plan = planner.decompose("mysterious_ore", {}, 1)

        assert len(plan) == 1
        assert plan[0].action == "collect"
        assert plan[0].target == "mysterious_ore"

    def test_dynamic_recipe_with_table(self, monkeypatch):
        """Dynamic recipe needing table should include crafting_table step."""
        from src.gaming.planner import HierarchicalPlanner
        from src.gaming import knowledge_base

        # Recipe that needs a crafting table
        monkeypatch.setattr(
            knowledge_base,
            "get_knowledge_base",
            lambda: type("KB", (), {
                "lookup_recipe": lambda self, item: {
                    "ingredients": {"iron_ingot": 3, "stick": 2},
                    "source": "test",
                    "needs_table": True,
                } if item == "iron_pickaxe_v2" else None
            })(),
        )

        planner = HierarchicalPlanner()
        plan = planner.decompose("iron_pickaxe_v2", {}, 1)

        targets = [s.target for s in plan]
        # Should include crafting_table if not in inventory
        assert "crafting_table" in targets or any("table" in t for t in targets)
