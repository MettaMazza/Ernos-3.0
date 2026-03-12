import sys
import pytest
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock

# Mock psutil before importing modules that depend on it
sys.modules["psutil"] = MagicMock()

from src.lobes.strategy.skill_forge import SkillForge, SAFE_TOOL_WHITELIST

TEST_FORGE_DIR = Path("tests/temp_forge")
TEST_USER_DIR = Path("tests/temp_users")
TEST_PENDING_DIR = TEST_FORGE_DIR / "pending"

@pytest.fixture
def clean_forge():
    # Setup
    if TEST_FORGE_DIR.exists():
        shutil.rmtree(TEST_FORGE_DIR)
    if TEST_USER_DIR.exists():
        shutil.rmtree(TEST_USER_DIR)
        
    TEST_FORGE_DIR.mkdir(parents=True)
    TEST_USER_DIR.mkdir(parents=True)
    
    # Patch paths
    import src.lobes.strategy.skill_forge as mod
    orig_pending = mod.SkillForge.PENDING_DIR
    orig_forge = mod.SkillForge.FORGE_DIR
    
    mod.SkillForge.PENDING_DIR = TEST_PENDING_DIR
    mod.SkillForge.FORGE_DIR = TEST_FORGE_DIR
    mod.SkillForge.QUEUE_FILE = TEST_FORGE_DIR / "pending.json"
    mod.SkillForge.LOG_FILE = TEST_FORGE_DIR / "forge_log.json"
    
    # Monkeypatch write_skill_file target dir logic
    # Actually, the class uses hardcoded "memory/users/" logic in _write_skill_file
    # We might need to subclass or mock Path...
    # Or simpler: Just update the method or path handling in the test?
    
    # Let's subclass to override paths for users
    class TestSkillForge(SkillForge):
        def _write_skill_file(self, proposal):
            if proposal["status"] == "active":
                target_dir = TEST_USER_DIR / proposal["user_id"] / "skills" / proposal["name"]
            else:
                target_dir = self.PENDING_DIR / proposal["name"]
            
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / "SKILL.md"
            
            tools_list = "\n".join([f"  - {t}" for t in proposal["allowed_tools"]])
            content = f"""---
name: {proposal["name"]}
description: {proposal["description"]}
version: 1.0.0
author: {proposal["user_id"]}
scope: {proposal["scope"]}
allowed_tools:
{tools_list}
---

{proposal["instructions"]}
"""
            target_file.write_text(content, encoding="utf-8")
            return target_file

    forge = TestSkillForge()
    yield forge
    
    # Teardown
    if TEST_FORGE_DIR.exists():
        shutil.rmtree(TEST_FORGE_DIR)
    if TEST_USER_DIR.exists():
        shutil.rmtree(TEST_USER_DIR)
        
    mod.SkillForge.PENDING_DIR = orig_pending
    mod.SkillForge.FORGE_DIR = orig_forge

def test_whitelist_constants():
    """Verify whitelist contains expected tools."""
    assert "read_file" in SAFE_TOOL_WHITELIST
    assert "search_web" in SAFE_TOOL_WHITELIST
    assert "run_command" not in SAFE_TOOL_WHITELIST
    assert "create_program" not in SAFE_TOOL_WHITELIST

def test_propose_safe_private(clean_forge):
    """Test safe private skill auto-approval."""
    res = clean_forge.propose_skill(
        name="test_safe",
        description="Safe skill",
        instructions="Read only",
        allowed_tools=["read_file"],
        scope="PRIVATE",
        user_id="U123"
    )
    
    assert res["status"] == "active"
    assert res["is_safe_whitelisted"] is True
    
    # Check file
    skill_path = Path(res["file_path"])
    assert skill_path.exists()
    assert "scope: PRIVATE" in skill_path.read_text()
    assert "name: test_safe" in skill_path.read_text()

def test_propose_unsafe_private(clean_forge):
    """Test unsafe private skill goes to pending."""
    res = clean_forge.propose_skill(
        name="test_unsafe",
        description="Unsafe skill",
        instructions="Run commands",
        allowed_tools=["run_command"],
        scope="PRIVATE",
        user_id="U123"
    )
    
    assert res["status"] == "pending"
    assert res["is_safe_whitelisted"] is False
    
    # Check file location (pending dir)
    skill_path = Path(res["file_path"])
    assert str(TEST_PENDING_DIR) in str(skill_path)

def test_propose_public_safe(clean_forge):
    """Test public safe skill goes to pending (all public are pending)."""
    res = clean_forge.propose_skill(
        name="test_public",
        description="Public skill",
        instructions="Read things",
        allowed_tools=["read_file"],
        scope="PUBLIC",
        user_id="U123"
    )
    
    assert res["status"] == "pending"
    
    skill_path = Path(res["file_path"])
    assert str(TEST_PENDING_DIR) in str(skill_path)
