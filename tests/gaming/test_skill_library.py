"""
Tests for Skill Library
"""

import pytest
import json
import os
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestSkill:
    """Tests for Skill dataclass."""
    
    def test_skill_creation(self):
        """Skill should be created with all fields."""
        from src.gaming.skill_library import Skill
        
        skill = Skill(
            name="get_iron_pickaxe",
            description="How to get iron pickaxe",
            goal="iron_pickaxe",
            steps=["collect log", "craft planks", "craft iron_pickaxe"],
            success_count=5,
            failure_count=1
        )
        
        assert skill.name == "get_iron_pickaxe"
        assert skill.goal == "iron_pickaxe"
        assert len(skill.steps) == 3
    
    def test_success_rate(self):
        """Success rate should calculate correctly."""
        from src.gaming.skill_library import Skill
        
        skill = Skill(
            name="test",
            description="test",
            goal="test",
            steps=[],
            success_count=8,
            failure_count=2
        )
        
        assert skill.success_rate == 0.8
    
    def test_success_rate_zero_uses(self):
        """Success rate should be 0 with no uses."""
        from src.gaming.skill_library import Skill
        
        skill = Skill(name="test", description="", goal="", steps=[])
        assert skill.success_rate == 0.0
    
    def test_to_dict(self):
        """to_dict should return serializable dict."""
        from src.gaming.skill_library import Skill
        
        skill = Skill(
            name="test",
            description="desc",
            goal="goal",
            steps=["a", "b"]
        )
        
        d = skill.to_dict()
        assert d["name"] == "test"
        assert d["steps"] == ["a", "b"]
        
        # Should be JSON serializable
        json.dumps(d)
    
    def test_from_dict(self):
        """from_dict should reconstruct Skill."""
        from src.gaming.skill_library import Skill
        
        data = {
            "name": "test",
            "description": "desc",
            "goal": "goal",
            "steps": ["a"],
            "success_count": 0,
            "failure_count": 0,
            "avg_duration": 0.0,
            "created_at": "",
            "last_used": ""
        }
        
        skill = Skill.from_dict(data)
        assert skill.name == "test"
        assert skill.steps == ["a"]


class TestSkillLibrary:
    """Tests for SkillLibrary class."""
    
    @pytest.fixture
    def temp_library(self, tmp_path):
        """Create a skill library with temp file."""
        from src.gaming.skill_library import SkillLibrary
        
        skills_file = str(tmp_path / "skills.json")
        return SkillLibrary(skills_file=skills_file)
    
    def test_store_new_skill(self, temp_library):
        """Storing should create new skill."""
        skill = temp_library.store(
            goal="iron_pickaxe",
            steps=["collect log", "craft planks", "craft pickaxe"],
            duration=120.0
        )
        
        assert skill.name == "get_iron_pickaxe"
        assert skill.success_count == 1
        assert skill.avg_duration == 120.0
    
    def test_store_updates_existing(self, temp_library):
        """Storing same goal should update existing skill."""
        temp_library.store("test", ["a", "b"], duration=100)
        temp_library.store("test", ["a", "b"], duration=200)
        
        skill = temp_library.retrieve("test")
        assert skill.success_count == 2
        assert skill.avg_duration == 150.0  # Average of 100 and 200
    
    def test_retrieve_exact_match(self, temp_library):
        """Retrieve should find exact match."""
        temp_library.store("diamond_sword", ["get diamond", "craft sword"])
        
        skill = temp_library.retrieve("diamond_sword")
        assert skill is not None
        assert skill.goal == "diamond_sword"
    
    def test_retrieve_not_found(self, temp_library):
        """Retrieve should return None if not found."""
        skill = temp_library.retrieve("nonexistent")
        assert skill is None
    
    def test_record_failure(self, temp_library):
        """Record failure should increment failure count."""
        temp_library.store("test", ["a"])
        temp_library.record_failure("test")
        
        skill = temp_library.retrieve("test")
        assert skill.failure_count == 1
    
    def test_persistence(self, tmp_path):
        """Skills should persist across library instances."""
        from src.gaming.skill_library import SkillLibrary
        
        skills_file = str(tmp_path / "persist_test.json")
        
        # Create and store
        lib1 = SkillLibrary(skills_file=skills_file)
        lib1.store("test_item", ["step1", "step2"])
        
        # Load in new instance
        lib2 = SkillLibrary(skills_file=skills_file)
        skill = lib2.retrieve("test_item")
        
        assert skill is not None
        assert skill.steps == ["step1", "step2"]
    
    def test_get_all(self, temp_library):
        """get_all should return all skills."""
        temp_library.store("a", ["1"])
        temp_library.store("b", ["2"])
        temp_library.store("c", ["3"])
        
        all_skills = temp_library.get_all()
        assert len(all_skills) == 3
    
    def test_get_best_skills(self, temp_library):
        """get_best_skills should sort by success rate."""
        # Store with different success rates
        temp_library.store("good", ["a"])
        temp_library.store("good", ["a"])  # 2 successes
        
        temp_library.store("bad", ["b"])
        temp_library.record_failure("bad")  # 1 success, 1 failure = 50%
        
        best = temp_library.get_best_skills(limit=2)
        assert best[0].goal == "good"  # 100% success
        assert best[1].goal == "bad"   # 50% success
    
    def test_delete(self, temp_library):
        """delete should remove skill."""
        temp_library.store("deleteme", ["a"])
        assert temp_library.retrieve("deleteme") is not None
        
        temp_library.delete("deleteme")
        assert temp_library.retrieve("deleteme") is None
    
    def test_clear(self, temp_library):
        """clear should remove all skills."""
        temp_library.store("a", ["1"])
        temp_library.store("b", ["2"])
        
        temp_library.clear()
        assert len(temp_library.get_all()) == 0
