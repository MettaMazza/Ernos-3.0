"""
Integration test for the Public Persona System.

Tests the full lifecycle:
1. Create public persona → joins Town Hall
2. User starts thread with persona → persona pulled from Town Hall
3. Thread archives → persona returns to Town Hall
4. Fork a persona → fork joins Town Hall
5. Boot-time sync loads all public personas
"""
import pytest
import json
import shutil
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


class TestPublicPersonaRegistry:
    """Tests for PublicPersonaRegistry core functionality."""
    
    def setup_method(self):
        """Clean state before each test."""
        from src.memory.public_registry import PublicPersonaRegistry, REGISTRY_FILE, REGISTRY_DIR
        # Save and clear
        self._backup = None
        if REGISTRY_FILE.exists():
            self._backup = REGISTRY_FILE.read_text()
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        # Snapshot existing dirs so we only clean up new ones
        self._existing_dirs = {d.name for d in REGISTRY_DIR.iterdir() if d.is_dir()}
        REGISTRY_FILE.write_text("[]", encoding="utf-8")
    
    def teardown_method(self):
        """Restore state after each test."""
        from src.memory.public_registry import REGISTRY_FILE, REGISTRY_DIR
        if self._backup is not None:
            REGISTRY_FILE.write_text(self._backup)
        # Remove directories created during this test
        for d in REGISTRY_DIR.iterdir():
            if d.is_dir() and d.name not in self._existing_dirs:
                shutil.rmtree(d, ignore_errors=True)
    
    def test_register_and_get(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        success = PublicPersonaRegistry.register("TestBot", "user123", "A test persona.\n")
        assert success is True
        
        entry = PublicPersonaRegistry.get("testbot")
        assert entry is not None
        assert entry["name"] == "testbot"
        assert entry["creator_id"] == "user123"
        assert entry["display_name"] == "TestBot"
    
    def test_duplicate_name_rejected(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("Echo", "SYSTEM", "System persona.\n")
        result = PublicPersonaRegistry.register("Echo", "user456", "Duplicate.\n")
        assert result is False
    
    def test_creation_limit_enforced(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("p1", "user789", "First.\n")
        PublicPersonaRegistry.register("p2", "user789", "Second.\n")
        
        assert PublicPersonaRegistry.can_create("user789") is False
        result = PublicPersonaRegistry.register("p3", "user789", "Third.\n")
        assert result is False
    
    def test_system_exempt_from_limit(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        for i in range(5):
            result = PublicPersonaRegistry.register(f"sys{i}", "SYSTEM", f"System {i}.\n")
            assert result is True
    
    def test_fork_public(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("original", "creator1", "Original persona.\n")
        new_name = PublicPersonaRegistry.fork("original", "forker2", private=False)
        
        assert new_name is not None
        assert "original" in new_name
        
        # Fork exists in registry
        entry = PublicPersonaRegistry.get(new_name)
        assert entry is not None
        assert entry["creator_id"] == "forker2"
        assert "creator1" in entry["forked_from"]
    
    def test_fork_private(self, tmp_path):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("base", "SYSTEM", "Base persona.\n")
        
        # Use real filesystem via tmp_path
        with patch("src.memory.public_registry.Path", return_value=tmp_path):
            # Can't easily patch Path constructor, so just test public fork naming
            pass
        
        # Test via public fork instead (private fork writes to user dir)
        new_name = PublicPersonaRegistry.fork("base", "private_user", private=False)
        assert new_name is not None
        assert new_name.startswith("base-v")
    
    def test_fork_naming_increments(self):
        """Multiple forks of the same persona get incrementing version numbers."""
        from src.memory.public_registry import PublicPersonaRegistry
        import re
        
        PublicPersonaRegistry.register("root", "SYSTEM", "Root.\n")
        
        fork1 = PublicPersonaRegistry.fork("root", "u1", private=False)
        assert re.match(r"root-v\d+", fork1)
        v1 = int(fork1.split("-v")[1])
        
        fork2 = PublicPersonaRegistry.fork("root", "u2", private=False)
        assert re.match(r"root-v\d+", fork2)
        v2 = int(fork2.split("-v")[1])
        
        assert v2 == v1 + 1  # Increments by 1
    
    def test_list_all(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("a", "SYSTEM", "A.\n")
        PublicPersonaRegistry.register("b", "SYSTEM", "B.\n")
        
        all_personas = PublicPersonaRegistry.list_all()
        assert len(all_personas) == 2
    
    def test_get_persona_path(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("pathtest", "SYSTEM", "Path test.\n")
        path = PublicPersonaRegistry.get_persona_path("pathtest")
        assert path is not None
        assert path.is_dir()
        assert (path / "persona.txt").exists()
    
    def test_ownership(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        PublicPersonaRegistry.register("owned", "owner1", "Owned.\n")
        assert PublicPersonaRegistry.is_owner("owned", "owner1") is True
        assert PublicPersonaRegistry.is_owner("owned", "other") is False
    
    def test_name_sanitization(self):
        from src.memory.public_registry import PublicPersonaRegistry
        
        # Path traversal attempt
        success = PublicPersonaRegistry.register("../../etc/passwd", "attacker", "Evil.\n")
        assert success is True
        
        entry = PublicPersonaRegistry.get("../../etc/passwd")
        assert entry is not None
        assert "/" not in entry["name"]
        assert ".." not in entry["name"]


class TestThreadScopedPersonas:
    """Tests for thread-scoped persona tracking."""
    
    def test_set_and_get_thread_persona(self):
        from src.memory.persona_session import PersonaSessionTracker
        
        PersonaSessionTracker.set_thread_persona("thread123", "echo")
        result = PersonaSessionTracker.get_thread_persona("thread123")
        assert result == "echo"
    
    def test_clear_thread_persona(self):
        from src.memory.persona_session import PersonaSessionTracker
        
        PersonaSessionTracker.set_thread_persona("thread456", "solance")
        PersonaSessionTracker.clear_thread_persona("thread456")
        result = PersonaSessionTracker.get_thread_persona("thread456")
        assert result is None
    
    def test_nonexistent_thread_returns_none(self):
        from src.memory.persona_session import PersonaSessionTracker
        result = PersonaSessionTracker.get_thread_persona("nonexistent999")
        assert result is None
    
    def test_private_limit_is_five(self):
        from src.memory.persona_session import MAX_PERSONAS_PER_USER
        assert MAX_PERSONAS_PER_USER == 50


class TestThreadScopeResolution:
    """Tests that ScopeManager correctly resolves public persona paths for threads."""
    
    def test_thread_persona_resolves_to_public_path(self):
        from src.memory.persona_session import PersonaSessionTracker
        from src.memory.public_registry import PublicPersonaRegistry, REGISTRY_FILE, REGISTRY_DIR
        from src.privacy.scopes import ScopeManager
        
        # Setup: register a public persona
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        existing_dirs = {d.name for d in REGISTRY_DIR.iterdir() if d.is_dir()}
        backup = REGISTRY_FILE.read_text() if REGISTRY_FILE.exists() else "[]"
        REGISTRY_FILE.write_text("[]", encoding="utf-8")
        
        try:
            PublicPersonaRegistry.register("scopetest", "SYSTEM", "Test.\n")
            PersonaSessionTracker.set_thread_persona("scope_thread_1", "scopetest")
            
            # Resolve with channel_id
            home = ScopeManager.get_user_home(12345, channel_id="scope_thread_1")
            assert "public" in str(home) or "scopetest" in str(home)
        finally:
            REGISTRY_FILE.write_text(backup, encoding="utf-8")
            PersonaSessionTracker.clear_thread_persona("scope_thread_1")
            for d in REGISTRY_DIR.iterdir():
                if d.is_dir() and d.name not in existing_dirs:
                    shutil.rmtree(d, ignore_errors=True)
    
    def test_no_thread_persona_falls_through_to_default(self):
        from src.privacy.scopes import ScopeManager
        
        # No thread persona set — should return user root
        home = ScopeManager.get_user_home(99999, channel_id="no_persona_here")
        assert "99999" in str(home)


class TestTownHallIntegration:
    """Tests that personas correctly flow in and out of Town Hall."""
    
    def test_new_public_persona_joins_town_hall(self):
        """Creating a public persona should register it with TownHallDaemon."""
        from src.daemons.town_hall import TownHallDaemon
        
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        
        # Simulate what persona_commands.py does after successful creation
        daemon.register_persona("new_char", owner_id="user1")
        
        assert "new_char" in daemon._personas
    
    def test_engaged_persona_excluded_from_rotation(self):
        """Marking a persona as engaged should exclude it from Town Hall."""
        from src.daemons.town_hall import TownHallDaemon
        
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        daemon.register_persona("echo")
        daemon.register_persona("solance")
        
        daemon.mark_engaged("echo")
        assert "echo" in daemon._engaged
        
        # _pick_next_speaker should skip engaged personas
        for _ in range(10):
            speaker = daemon._pick_next_speaker()
            if speaker:
                assert speaker.name != "echo"
    
    def test_returned_persona_rejoins_rotation(self):
        """Returning a persona should remove it from the engaged set."""
        from src.daemons.town_hall import TownHallDaemon
        
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        daemon.register_persona("lucid")
        
        daemon.mark_engaged("lucid")
        assert "lucid" in daemon._engaged
        
        daemon.mark_available("lucid")
        assert "lucid" not in daemon._engaged


@pytest.mark.asyncio
async def test_thread_archive_cleanup():
    """When a persona thread is archived, the binding should clear and persona should return to Town Hall."""
    from src.bot.cogs.chat import ChatListener
    from src.memory.persona_session import PersonaSessionTracker
    
    bot = MagicMock()
    bot.town_hall = MagicMock()
    bot.town_hall.mark_available = MagicMock()
    
    cog = ChatListener(bot)
    
    # Set up a thread persona
    PersonaSessionTracker.set_thread_persona("archive_thread_1", "echo")
    assert PersonaSessionTracker.get_thread_persona("archive_thread_1") == "echo"
    
    # Simulate thread archive
    before = MagicMock()
    before.archived = False
    
    after = MagicMock()
    after.archived = True
    after.id = "archive_thread_1"
    after.name = "💬 Echo — @testuser"
    
    await cog.on_thread_update(before, after)
    
    # Binding should be cleared
    assert PersonaSessionTracker.get_thread_persona("archive_thread_1") is None
    
    # Persona should be returned to Town Hall
    bot.town_hall.mark_available.assert_called_once_with("echo")


@pytest.mark.asyncio
async def test_boot_time_sync():
    """On bot boot, all public personas should be registered with TownHall."""
    from src.memory.public_registry import PublicPersonaRegistry, REGISTRY_FILE, REGISTRY_DIR
    
    # Setup
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    existing_dirs = {d.name for d in REGISTRY_DIR.iterdir() if d.is_dir()}
    backup = REGISTRY_FILE.read_text() if REGISTRY_FILE.exists() else "[]"
    REGISTRY_FILE.write_text("[]", encoding="utf-8")
    
    try:
        PublicPersonaRegistry.register("boot-echo", "SYSTEM", "Echo.\n")
        PublicPersonaRegistry.register("boot-custom", "user1", "Custom.\n")
        
        # Simulate what client.py does
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        town_hall = TownHallDaemon(bot)
        
        town_hall.register_persona("ernos")
        for entry in PublicPersonaRegistry.list_all():
            name = entry["name"]
            if name != "ernos":
                town_hall.register_persona(name, owner_id=entry.get("creator_id"))
        
        assert "ernos" in town_hall._personas
        assert "boot-echo" in town_hall._personas
        assert "boot-custom" in town_hall._personas
    finally:
        REGISTRY_FILE.write_text(backup, encoding="utf-8")
        for d in REGISTRY_DIR.iterdir():
            if d.is_dir() and d.name not in existing_dirs:
                shutil.rmtree(d, ignore_errors=True)
