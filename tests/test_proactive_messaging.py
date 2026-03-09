"""
Tests for Proactive Messaging — Inbox, Outreach Delivery, Town Hall.
"""
import pytest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# === Inbox Tests ===

class TestInbox:
    """Test InboxManager CRUD, priority, and filtering."""
    
    def setup_method(self):
        """Set up a temp memory directory."""
        self.test_dir = Path("memory/users/99999")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def teardown_method(self):
        """Clean up."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_add_message(self):
        from src.memory.inbox import InboxManager
        msg = InboxManager.add_message(99999, "luna", "Hello from Luna!")
        assert msg is not None
        assert msg["persona"] == "luna"
        assert msg["content"] == "Hello from Luna!"
        assert msg["read"] is False
        assert msg["priority"] == "normal"
    
    def test_add_message_from_ernos(self):
        from src.memory.inbox import InboxManager
        msg = InboxManager.add_message(99999, "ernos", "Thinking of you!")
        assert msg is not None
        assert msg["persona"] == "ernos"
    
    def test_unread_count(self):
        from src.memory.inbox import InboxManager
        InboxManager.add_message(99999, "luna", "Message 1")
        InboxManager.add_message(99999, "luna", "Message 2")
        InboxManager.add_message(99999, "kai", "Message 3")
        
        counts = InboxManager.get_unread_count(99999)
        assert counts["luna"] == 2
        assert counts["kai"] == 1
    
    def test_mark_read(self):
        from src.memory.inbox import InboxManager
        msg = InboxManager.add_message(99999, "luna", "Read me!")
        InboxManager.mark_read(99999, msg["id"])
        
        unread = InboxManager.get_unread(99999)
        assert len(unread) == 0
    
    def test_mark_all_read(self):
        from src.memory.inbox import InboxManager
        InboxManager.add_message(99999, "luna", "A")
        InboxManager.add_message(99999, "kai", "B")
        
        count = InboxManager.mark_all_read(99999)
        assert count == 2
        assert len(InboxManager.get_unread(99999)) == 0
    
    def test_mark_read_by_persona(self):
        from src.memory.inbox import InboxManager
        InboxManager.add_message(99999, "luna", "A")
        InboxManager.add_message(99999, "kai", "B")
        
        count = InboxManager.mark_all_read(99999, persona="luna")
        assert count == 1
        
        unread = InboxManager.get_unread(99999)
        assert len(unread) == 1
        assert unread[0]["persona"] == "kai"
    
    def test_filter_by_persona(self):
        from src.memory.inbox import InboxManager
        InboxManager.add_message(99999, "luna", "Luna msg")
        InboxManager.add_message(99999, "kai", "Kai msg")
        
        luna_msgs = InboxManager.get_unread(99999, persona="luna")
        assert len(luna_msgs) == 1
        assert luna_msgs[0]["persona"] == "luna"
    
    def test_priority_default(self):
        from src.memory.inbox import InboxManager
        p = InboxManager.get_priority(99999, "luna")
        assert p == "normal"
    
    def test_set_priority_notify(self):
        from src.memory.inbox import InboxManager
        InboxManager.set_priority(99999, "luna", "notify")
        
        msg = InboxManager.add_message(99999, "luna", "Notified!")
        assert msg["priority"] == "notify"
    
    def test_set_priority_mute(self):
        from src.memory.inbox import InboxManager
        InboxManager.set_priority(99999, "luna", "mute")
        
        msg = InboxManager.add_message(99999, "luna", "Blocked!")
        assert msg is None  # Muted personas can't add
    
    def test_set_priority_invalid(self):
        from src.memory.inbox import InboxManager
        result = InboxManager.set_priority(99999, "luna", "invalid")
        assert "❌" in result
    
    def test_inbox_summary(self):
        from src.memory.inbox import InboxManager
        InboxManager.add_message(99999, "luna", "Hello")
        summary = InboxManager.get_inbox_summary(99999)
        assert "📬" in summary
        assert "luna" in summary
    
    def test_inbox_summary_empty(self):
        from src.memory.inbox import InboxManager
        summary = InboxManager.get_inbox_summary(99999)
        assert "📭" in summary
    
    def test_get_all_priorities(self):
        from src.memory.inbox import InboxManager
        InboxManager.set_priority(99999, "luna", "notify")
        InboxManager.set_priority(99999, "kai", "mute")
        
        priorities = InboxManager.get_all_priorities(99999)
        assert priorities["luna"] == "notify"
        assert priorities["kai"] == "mute"


# === Outreach Delivery Tests ===

class TestOutreachDelivery:
    """Test OutreachManager.deliver_outreach routing."""
    
    @pytest.mark.asyncio
    async def test_deliver_public_ernos(self):
        """Ernos public outreach → posts to channel."""
        from src.memory.outreach import OutreachManager
        from src.memory.relationships import RelationshipData
        
        mock_channel = AsyncMock()
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        
        # Create mock relationship data
        data = RelationshipData(user_id=88888)
        data.outreach_settings = {"ernos": {"policy": "public", "frequency": "unlimited", "last_outreach": None}}
        
        with patch.object(OutreachManager, 'can_outreach', return_value=(True, "")), \
             patch('src.memory.relationships.RelationshipManager.load_data', return_value=data), \
             patch('src.memory.relationships.RelationshipManager.save_data'), \
             patch('config.settings.OUTREACH_CHANNEL_ID', 123456):
            
            success, reason = await OutreachManager.deliver_outreach(
                mock_bot, 88888, "ernos", "Hello everyone!", scope="public"
            )
            assert success is True
            assert "public" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_deliver_private_inbox(self):
        """Private outreach → queued to inbox."""
        from src.memory.outreach import OutreachManager
        from src.memory.relationships import RelationshipData
        
        # Ensure test dir exists
        test_dir = Path("memory/users/88888")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        data = RelationshipData(user_id=88888)
        data.outreach_settings = {"luna": {"policy": "private", "frequency": "unlimited", "last_outreach": None}}
        
        try:
            with patch.object(OutreachManager, 'can_outreach', return_value=(True, "")), \
                 patch('src.memory.relationships.RelationshipManager.load_data', return_value=data), \
                 patch('src.memory.relationships.RelationshipManager.save_data'):
                
                mock_bot = MagicMock()
                success, reason = await OutreachManager.deliver_outreach(
                    mock_bot, 88888, "luna", "Private message", scope="private"
                )
                assert success is True
                assert "ok" in reason.lower()
        finally:
            if test_dir.exists():
                shutil.rmtree(test_dir)
    
    @pytest.mark.asyncio
    async def test_deliver_blocked_by_none_policy(self):
        """scope='none' blocks outreach."""
        from src.memory.outreach import OutreachManager
        from src.memory.relationships import RelationshipData
        
        data = RelationshipData(user_id=88888)
        data.outreach_settings = {"ernos": {"policy": "none", "frequency": "medium", "last_outreach": None}}
        
        with patch.object(OutreachManager, 'can_outreach', return_value=(True, "")), \
             patch('src.memory.relationships.RelationshipManager.load_data', return_value=data):
            
            mock_bot = MagicMock()
            success, reason = await OutreachManager.deliver_outreach(
                mock_bot, 88888, "ernos", "Blocked!"
            )
            assert success is False
    
    @pytest.mark.asyncio
    async def test_deliver_blocked_by_timing(self):
        """Timing gate prevents outreach."""
        from src.memory.outreach import OutreachManager
        from src.memory.relationships import RelationshipData
        
        data = RelationshipData(user_id=88888)
        
        with patch.object(OutreachManager, 'can_outreach', return_value=(False, "Too soon")), \
             patch('src.memory.relationships.RelationshipManager.load_data', return_value=data):
            
            mock_bot = MagicMock()
            success, reason = await OutreachManager.deliver_outreach(
                mock_bot, 88888, "ernos", "Too early!"
            )
            assert success is False
    
    @pytest.mark.asyncio
    async def test_ernos_private_dm_allowed(self):
        """Ernos can also DM privately (not just public)."""
        from src.memory.outreach import OutreachManager
        from src.memory.relationships import RelationshipData
        
        test_dir = Path("memory/users/88888")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        data = RelationshipData(user_id=88888)
        data.outreach_settings = {"ernos": {"policy": "private", "frequency": "unlimited", "last_outreach": None}}
        
        try:
            with patch.object(OutreachManager, 'can_outreach', return_value=(True, "")), \
                 patch('src.memory.relationships.RelationshipManager.load_data', return_value=data), \
                 patch('src.memory.relationships.RelationshipManager.save_data'):
                
                mock_bot = MagicMock()
                success, reason = await OutreachManager.deliver_outreach(
                    mock_bot, 88888, "ernos", "Private from Ernos", scope="private"
                )
                assert success is True
                assert "ok" in reason.lower()
        finally:
            if test_dir.exists():
                shutil.rmtree(test_dir)


# === Town Hall Tests ===

class TestPersonaAgent:
    """Test PersonaAgent memory silo operations."""
    
    def setup_method(self):
        self.test_dir = Path("memory/system/town_hall/personas/testpersona")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def teardown_method(self):
        base = Path("memory/system/town_hall")
        if base.exists():
            shutil.rmtree(base)
    
    def test_init_creates_silo(self):
        from src.daemons.town_hall import PersonaAgent
        agent = PersonaAgent("luna_test")
        assert (agent._home / "context.jsonl").exists()
        assert (agent._home / "lessons.json").exists()
        assert (agent._home / "opinions.json").exists()
        assert (agent._home / "relationships.json").exists()
    
    def test_record_and_get_context(self):
        from src.daemons.town_hall import PersonaAgent
        agent = PersonaAgent("luna_test")
        agent.record_message("kai", "Hello Luna!")
        agent.record_message("luna_test", "Hey Kai!")
        
        ctx = agent.get_context()
        assert len(ctx) == 2
        assert ctx[0]["speaker"] == "kai"
        assert ctx[1]["speaker"] == "luna_test"
    
    def test_opinions(self):
        from src.daemons.town_hall import PersonaAgent
        agent = PersonaAgent("luna_test")
        agent.save_opinion("creativity", "It's the core of existence")
        
        ops = agent.get_opinions()
        assert "creativity" in ops
        assert "core" in ops["creativity"]["opinion"]
    
    def test_relationships(self):
        from src.daemons.town_hall import PersonaAgent
        agent = PersonaAgent("luna_test")
        agent.update_relationship("kai", "We have great discussions!")
        
        rels = agent.get_relationships()
        assert "kai" in rels
        assert "great" in rels["kai"]["sentiment"]
    
    def test_lessons(self):
        from src.daemons.town_hall import PersonaAgent
        agent = PersonaAgent("luna_test")
        agent.add_lesson("Disagreement can be productive")
        
        lessons = agent.get_lessons()
        assert len(lessons) == 1
        assert "productive" in lessons[0]
    
    def test_default_character(self):
        from src.daemons.town_hall import PersonaAgent
        agent = PersonaAgent("brand_new")
        char = agent.get_character()
        assert "Brand_New" in char or "brand_new" in char.lower()


class TestTownHallDaemon:
    """Test TownHallDaemon operations."""
    
    def setup_method(self):
        self.test_dir = Path("memory/system/town_hall")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def teardown_method(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_register_persona(self):
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        
        agent = daemon.register_persona("Luna")
        assert "luna" in daemon._personas
        assert agent.name == "luna"
    
    def test_engaged_filtering(self):
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        
        daemon.register_persona("Luna")
        daemon.register_persona("Kai")
        daemon.register_persona("Nova")
        
        daemon.mark_engaged("luna")
        
        available = daemon._get_available_personas()
        names = [p.name for p in available]
        assert "luna" not in names
        assert "kai" in names
        assert "nova" in names
    
    def test_rejoin_after_engaged(self):
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        
        daemon.register_persona("Luna")
        daemon.mark_engaged("luna")
        assert len(daemon._get_available_personas()) == 0
        
        daemon.mark_available("luna")
        assert len(daemon._get_available_personas()) == 1
    
    def test_pick_avoids_last_speaker(self):
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        
        daemon.register_persona("Luna")
        daemon.register_persona("Kai")
        daemon._last_speaker = "luna"
        
        # Run 10 times — should pick kai every time with 2 personas
        for _ in range(10):
            speaker = daemon._pick_next_speaker()
            assert speaker.name == "kai"
    
    def test_status_report(self):
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        
        daemon.register_persona("Luna")
        daemon.register_persona("Kai")
        daemon.mark_engaged("luna")
        
        status = daemon.get_status()
        assert "1 available" in status
        assert "1 engaged" in status
        assert "Personas: 2" in status
    
    def test_history_recording(self):
        from src.daemons.town_hall import TownHallDaemon
        bot = MagicMock()
        daemon = TownHallDaemon(bot)
        daemon._topic = "Test topic"
        
        daemon._record_history("luna", "Hello everyone!")
        
        history = daemon.get_recent_history()
        assert len(history) == 1
        assert history[0]["speaker"] == "luna"
        assert history[0]["topic"] == "Test topic"
    
    def test_persona_color_deterministic(self):
        from src.daemons.town_hall import TownHallDaemon
        c1 = TownHallDaemon._persona_color("luna")
        c2 = TownHallDaemon._persona_color("luna")
        c3 = TownHallDaemon._persona_color("kai")
        
        assert c1 == c2  # Same name → same color
        assert c1 != c3  # Different names → different colors (with high probability)
    
    def test_topic_generation(self):
        from src.daemons.town_hall import TownHallDaemon
        import asyncio
        bot = MagicMock()
        bot.engine_manager = MagicMock()
        daemon = TownHallDaemon(bot)
        
        topic = asyncio.run(daemon._generate_topic())
        assert isinstance(topic, str)
        assert len(topic) > 10
