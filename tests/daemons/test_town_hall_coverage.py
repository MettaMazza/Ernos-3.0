"""
Coverage tests for daemons/town_hall.py — PersonaAgent + TownHallDaemon.
All async patterns properly mocked to prevent hanging.
"""
import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, Mock, patch
from src.daemons.town_hall import PersonaAgent, TownHallDaemon


# ──────────────────────────────────────
# PersonaAgent
# ──────────────────────────────────────

@pytest.fixture
def persona(tmp_path):
    with patch.object(PersonaAgent, "TOWN_HALL_DIR", tmp_path):
        p = PersonaAgent("TestBot", owner_id="owner123")
        yield p
        if p._home.exists():
            shutil.rmtree(p._home)


class TestPersonaAgentInit:
    def test_name_lowered(self, persona):
        assert persona.name == "testbot"

    def test_display_name(self, persona):
        assert persona.display_name == "Testbot"

    def test_silo_created(self, persona):
        assert (persona._home / "context.jsonl").exists()
        assert (persona._home / "lessons.json").exists()
        assert (persona._home / "opinions.json").exists()
        assert (persona._home / "relationships.json").exists()


class TestGetCharacter:
    def test_fallback(self, persona):
        assert "Testbot" in persona.get_character()

    def test_from_silo(self, persona):
        (persona._home / "persona.txt").write_text(
            "I am a rich and complex character with deep personality and many traits."
        )
        assert "rich and complex" in persona.get_character()

    def test_short_content_skipped(self, persona):
        (persona._home / "persona.txt").write_text("short")
        assert "Testbot" in persona.get_character()


class TestGetContext:
    def test_empty(self, persona):
        assert persona.get_context() == []

    def test_with_entries(self, persona):
        ctx = persona._home / "context.jsonl"
        entries = [json.dumps({"speaker": "a", "content": f"m{i}"}) for i in range(5)]
        ctx.write_text("\n".join(entries))
        assert len(persona.get_context(limit=3)) == 3

    def test_bad_json(self, persona):
        (persona._home / "context.jsonl").write_text('bad\n{"speaker":"a","content":"ok"}\n')
        assert len(persona.get_context()) == 1


class TestRecordMessage:
    def test_records(self, persona):
        persona.record_message("alice", "hello")
        ctx = persona.get_context()
        assert len(ctx) == 1 and ctx[0]["speaker"] == "alice"

    def test_truncates(self, persona):
        persona.record_message("a", "x" * 10000)
        assert len(persona.get_context()[0]["content"]) == 5000

    def test_trims_old(self, persona):
        f = persona._home / "context.jsonl"
        f.write_text("\n".join(json.dumps({"speaker": "a", "content": f"m{i}", "timestamp": "t"})
                               for i in range(210)) + "\n")
        persona.record_message("a", "new")
        assert len(f.read_text().strip().split("\n")) <= 201


class TestOpinions:
    def test_empty(self, persona):
        assert persona.get_opinions() == {}

    def test_save_get(self, persona):
        persona.save_opinion("ethics", "important")
        assert "ethics" in persona.get_opinions()

    def test_truncates(self, persona):
        persona.save_opinion("t", "x" * 5000)
        assert len(persona.get_opinions()["t"]["opinion"]) == 2000

    def test_caps_50(self, persona):
        for i in range(55):
            persona.save_opinion(f"t{i}", f"o{i}")
        assert len(persona.get_opinions()) <= 50


class TestRelationships:
    def test_empty(self, persona):
        assert persona.get_relationships() == {}

    def test_update(self, persona):
        persona.update_relationship("Alice", "friendly")
        assert "alice" in persona.get_relationships()


class TestLessons:
    def test_empty(self, persona):
        assert persona.get_lessons() == []

    def test_add(self, persona):
        persona.add_lesson("be kind")
        assert "be kind" in persona.get_lessons()

    def test_truncates(self, persona):
        persona.add_lesson("x" * 2000)
        assert len(persona.get_lessons()[0]) == 1000

    def test_caps_50(self, persona):
        for i in range(55):
            persona.add_lesson(f"l{i}")
        assert len(persona.get_lessons()) <= 50


# ──────────────────────────────────────
# TownHallDaemon
# ──────────────────────────────────────

@pytest.fixture
def daemon(tmp_path):
    bot = MagicMock()
    bot.tape_engine = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    engine = MagicMock()
    engine.__class__.__name__ = "TestEngine"
    bot.engine_manager.get_active_engine.return_value = engine
    with patch.object(TownHallDaemon, "HISTORY_FILE", tmp_path / "history.jsonl"):
        d = TownHallDaemon(bot)
        yield d


class TestTownHallInit:
    def test_defaults(self, daemon):
        assert not daemon.is_running
        assert daemon._personas == {}
        assert daemon._conversation_turns == 0


class TestSuggestions:
    def test_add_get(self, daemon):
        assert daemon.add_suggestion("u1", ["What is AI?", "Philosophy"]) == 2
        assert daemon.get_suggestion() == "What is AI?"

    def test_short_skipped(self, daemon):
        assert daemon.add_suggestion("u1", ["ok", ""]) == 0

    def test_empty(self, daemon):
        assert daemon.get_suggestion() is None


class TestRegisterPersona:
    def test_registers(self, daemon, tmp_path):
        with patch.object(PersonaAgent, "TOWN_HALL_DIR", tmp_path):
            a = daemon.register_persona("Alice")
        assert "alice" in daemon._personas
        if a._home.exists():
            shutil.rmtree(a._home)


class TestEngagement:
    def test_mark_engaged(self, daemon):
        daemon.mark_engaged("Alice")
        assert "alice" in daemon._engaged

    def test_mark_available(self, daemon):
        daemon._engaged.add("alice")
        daemon.mark_available("Alice")
        assert "alice" not in daemon._engaged


class TestAvailablePersonas:
    def test_all(self, daemon):
        p1 = MagicMock(); p1.name = "a"
        p2 = MagicMock(); p2.name = "b"
        daemon._personas = {"a": p1, "b": p2}
        assert len(daemon._get_available_personas()) == 2

    def test_engaged(self, daemon):
        p1 = MagicMock(); p1.name = "a"
        p2 = MagicMock(); p2.name = "b"
        daemon._personas = {"a": p1, "b": p2}
        daemon._engaged.add("a")
        r = daemon._get_available_personas()
        assert len(r) == 1 and r[0].name == "b"


class TestPickNextSpeaker:
    def test_none(self, daemon):
        assert daemon._pick_next_speaker() is None

    def test_avoids_last(self, daemon):
        p1 = MagicMock(); p1.name = "a"
        p2 = MagicMock(); p2.name = "b"
        daemon._personas = {"a": p1, "b": p2}
        daemon._last_speaker = "a"
        with patch("random.choice", side_effect=lambda x: x[0]):
            assert daemon._pick_next_speaker().name == "b"

    def test_only_last(self, daemon):
        p = MagicMock(); p.name = "a"
        daemon._personas = {"a": p}
        daemon._last_speaker = "a"
        with patch("random.choice", side_effect=lambda x: x[0]):
            assert daemon._pick_next_speaker().name == "a"


class TestGenerateTopic:
    @pytest.mark.asyncio
    async def test_suggestion_priority(self, daemon):
        daemon._suggested_topics.append({"topic": "User topic", "suggested_by": "u1", "timestamp": "t"})
        assert await daemon._generate_topic() == "User topic"

    @pytest.mark.asyncio
    async def test_seed_fallback(self, daemon):
        with patch("random.choices", return_value=["seed"]):
            result = await daemon._generate_topic()
        assert isinstance(result, str) and len(result) > 5


class TestStop:
    def test_stop(self, daemon):
        daemon.is_running = True
        daemon.stop()
        assert not daemon.is_running


class TestFallback:
    @pytest.mark.asyncio
    async def test_success(self, daemon):
        daemon._topic = "test"
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="Fallback!")
        sp = MagicMock()
        sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "I am A."
        sp.get_context.return_value = []
        assert await daemon._generate_persona_response_fallback(sp) == "Fallback!"

    @pytest.mark.asyncio
    async def test_exception(self, daemon):
        daemon._topic = "test"
        daemon.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("err"))
        sp = MagicMock()
        sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "x"; sp.get_context.return_value = []
        assert await daemon._generate_persona_response_fallback(sp) is None

    @pytest.mark.asyncio
    async def test_strips_prefix(self, daemon):
        daemon._topic = "test"
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="Alice: Hello world")
        sp = MagicMock()
        sp.name = "alice"; sp.display_name = "Alice"
        sp.get_character.return_value = "x"; sp.get_context.return_value = []
        assert await daemon._generate_persona_response_fallback(sp) == "Hello world"


class TestPostToChannel:
    @pytest.mark.asyncio
    async def test_no_channel(self, daemon):
        mock_settings = MagicMock()
        mock_settings.PERSONA_CHAT_CHANNEL_ID = 0
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            await daemon._post_to_channel("A", "Hello")
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_with_channel(self, daemon):
        mock_settings = MagicMock()
        mock_settings.PERSONA_CHAT_CHANNEL_ID = 12345
        ch = AsyncMock()
        daemon.bot.get_channel.return_value = ch
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await daemon._post_to_channel("A", "Hello")
        ch.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_fallback(self, daemon):
        mock_settings = MagicMock()
        mock_settings.PERSONA_CHAT_CHANNEL_ID = 12345
        daemon.bot.get_channel.return_value = None
        ch = AsyncMock()
        daemon.bot.fetch_channel = AsyncMock(return_value=ch)
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await daemon._post_to_channel("A", "Hello")
        assert True  # No exception: async operation completed within timeout


class TestChunkAtSentences:
    def test_short(self):
        assert TownHallDaemon._chunk_at_sentences("hi", 100) == ["hi"]

    def test_sentence_boundary(self):
        text = "A" * 100 + ". " + "B" * 50
        r = TownHallDaemon._chunk_at_sentences(text, 110)
        assert len(r) == 2

    def test_space_fallback(self):
        text = "word " * 60
        assert len(TownHallDaemon._chunk_at_sentences(text, 100)) > 1

    def test_no_boundaries(self):
        assert len(TownHallDaemon._chunk_at_sentences("A" * 300, 100)) == 3


class TestRecordHistory:
    def test_records(self, daemon):
        daemon._topic = "test"
        daemon._record_history("a", "hello")
        entry = json.loads(daemon.HISTORY_FILE.read_text().strip())
        assert entry["speaker"] == "a"

    def test_trims(self, daemon):
        daemon._topic = "t"
        lines = [json.dumps({"speaker": "a", "content": f"m{i}", "topic": "t", "timestamp": "t"})
                 for i in range(510)]
        daemon.HISTORY_FILE.write_text("\n".join(lines) + "\n")
        daemon._record_history("a", "new")
        assert len(daemon.HISTORY_FILE.read_text().strip().split("\n")) <= 501


class TestPersonaColor:
    def test_deterministic(self):
        assert TownHallDaemon._persona_color("a") == TownHallDaemon._persona_color("a")

    def test_is_int(self):
        assert isinstance(TownHallDaemon._persona_color("bob"), int)


class TestGetRecentHistory:
    def test_empty(self, daemon):
        assert daemon.get_recent_history() == []

    def test_with_entries(self, daemon):
        entries = [json.dumps({"speaker": "a", "content": f"m{i}"}) for i in range(5)]
        daemon.HISTORY_FILE.write_text("\n".join(entries) + "\n")
        assert len(daemon.get_recent_history(limit=3)) == 3

    def test_json_decode_error(self, daemon):
        # Triggers lines 329-331 in town_hall.py (suppressed JSON decode error)
        daemon.HISTORY_FILE.write_text("invalid json\n")
        assert len(daemon.get_recent_history(limit=3)) == 0


class TestGetStatus:
    def test_stopped(self, daemon):
        s = daemon.get_status()
        assert "Stopped" in s

    def test_running(self, daemon):
        daemon.is_running = True
        p = MagicMock(); p.name = "a"
        daemon._personas = {"a": p}
        daemon._topic = "AI"
        daemon._conversation_turns = 5
        s = daemon.get_status()
        assert "Running" in s and "AI" in s


# ──────────────────────────────────────
# Additional coverage — uncovered paths
# ──────────────────────────────────────

class AsyncIter:
    """Helper for mocking async for loops."""
    def __init__(self, items):
        self._items = list(items)
    def __aiter__(self):
        return self
    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class TestGetCharacterOwnerFile:
    """Covers lines 82-84: owner persona file path."""
    def test_owner_file_valid(self, tmp_path, monkeypatch):
        # get_character uses relative Path("memory/users/...") so we chdir to tmp_path
        monkeypatch.chdir(tmp_path)
        owner_dir = tmp_path / "memory" / "users" / "owner1" / "personas" / "mybot"
        owner_dir.mkdir(parents=True)
        (owner_dir / "persona.txt").write_text(
            "I am a comprehensive owner-defined persona with many unique traits and quirks."
        )
        with patch.object(PersonaAgent, "TOWN_HALL_DIR", tmp_path):
            p = PersonaAgent("MyBot", owner_id="owner1")
            char = p.get_character()
            assert "comprehensive owner-defined" in char
        if p._home.exists():
            shutil.rmtree(p._home)


class TestGetCharacterPublicFile:
    """Covers lines 96-98: public persona registry path."""
    def test_public_persona(self, tmp_path):
        pub_dir = tmp_path / "memory" / "public" / "personas" / "publicbot"
        pub_dir.mkdir(parents=True)
        (pub_dir / "persona.txt").write_text(
            "A detailed public persona definition with rich character depth and history."
        )
        with patch.object(PersonaAgent, "TOWN_HALL_DIR", tmp_path):
            p = PersonaAgent("PublicBot")
            original_path = Path
            def patched_path(*args):
                result = original_path(*args)
                s = str(result)
                if "memory/public/personas/" in s:
                    return tmp_path / s
                return result
            with patch("src.daemons.persona_agent.Path", side_effect=patched_path):
                char = p.get_character()
            assert "detailed public persona" in char
        if p._home.exists():
            shutil.rmtree(p._home)


class TestGenerateTopicLLM:
    """Covers lines 289-310: LLM topic generation."""
    @pytest.mark.asyncio
    async def test_llm_with_history(self, daemon):
        entries = [json.dumps({"speaker": "a", "content": f"msg{i}"}) for i in range(5)]
        daemon.HISTORY_FILE.write_text("\n".join(entries) + "\n")
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="LLM generated topic here")

        with patch("random.choices", return_value=["llm"]):
            result = await daemon._generate_topic()
        assert result == "LLM generated topic here"

    @pytest.mark.asyncio
    async def test_llm_no_history(self, daemon):
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="")
        with patch("random.choices", return_value=["llm"]):
            result = await daemon._generate_topic()
        # Falls through to seed
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_llm_exception(self, daemon):
        entries = [json.dumps({"speaker": "a", "content": "hi"}) for _ in range(5)]
        daemon.HISTORY_FILE.write_text("\n".join(entries) + "\n")
        daemon.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM down"))

        with patch("random.choices", return_value=["llm"]):
            result = await daemon._generate_topic()
        # Falls to seed
        assert isinstance(result, str)


class TestGenerateTopicExternal:
    """Covers lines 314-329: external wisdom topic."""
    @pytest.mark.asyncio
    async def test_external_with_wisdom(self, daemon, tmp_path):
        wisdom_dir = tmp_path / "core"
        wisdom_dir.mkdir(parents=True)
        wisdom = wisdom_dir / "realizations.txt"
        wisdom.write_text(
            '[2026] ```json\n{"topic": "AI Ethics", "truth": "AI is wonderful"}\n```\n'
            '[2026] ```json\n{"topic": "Consciousness", "truth": "Consciousness matters"}\n```\n'
        )

        with patch("random.choices", return_value=["external"]), \
             patch("src.daemons.town_hall_generation.data_dir", return_value=tmp_path):
            result = await daemon._generate_topic()
        assert "realized" in result or "think" in result.lower()

    @pytest.mark.asyncio
    async def test_external_no_file(self, daemon, tmp_path):
        with patch("random.choices", return_value=["external"]), \
             patch("src.daemons.town_hall_generation.data_dir", return_value=tmp_path):
            result = await daemon._generate_topic()
        # Falls to seed
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_external_wisdom_without_truth(self, daemon, tmp_path):
        wisdom_dir = tmp_path / "core"
        wisdom_dir.mkdir(parents=True)
        wisdom = wisdom_dir / "realizations.txt"
        wisdom.write_text('[2026] ```json\n{"topic": "AI Ethics"}\n```\n')
        with patch("random.choices", return_value=["external"]), \
             patch("src.daemons.town_hall_generation.data_dir", return_value=tmp_path):
            result = await daemon._generate_topic()
        assert "Ernos has been thinking about" in result

    @pytest.mark.asyncio
    async def test_external_wisdom_bad_json(self, daemon, tmp_path):
        wisdom_dir = tmp_path / "core"
        wisdom_dir.mkdir(parents=True)
        wisdom = wisdom_dir / "realizations.txt"
        wisdom.write_text('[2026] ```json\n{bad_json}\n```\n')
        with patch("random.choices", return_value=["external"]), \
             patch("src.daemons.town_hall_generation.data_dir", return_value=tmp_path):
            result = await daemon._generate_topic()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_external_wisdom_exception(self, daemon, tmp_path):
        with patch("random.choices", return_value=["external"]), \
             patch("src.daemons.town_hall_generation.data_dir", side_effect=Exception("Read error")):
            result = await daemon._generate_topic()
        assert isinstance(result, str)


class TestGenerateTopicPersona:
    """Covers lines 333-353: persona-driven topic."""
    @pytest.mark.asyncio
    async def test_persona_topic(self, daemon):
        p = MagicMock(); p.name = "alice"; p.display_name = "Alice"
        p.get_character.return_value = "I am Alice."
        daemon._personas = {"alice": p}
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="A deep philosophical question")

        with patch("random.choices", return_value=["persona"]), \
             patch("random.choice", return_value=p):
            result = await daemon._generate_topic()
        assert "Alice asks:" in result

    @pytest.mark.asyncio
    async def test_persona_no_speaker(self, daemon):
        with patch("random.choices", return_value=["persona"]):
            result = await daemon._generate_topic()
        assert isinstance(result, str)  # seed fallback

    @pytest.mark.asyncio
    async def test_persona_exception(self, daemon):
        p = MagicMock(); p.name = "a"; p.display_name = "A"
        p.get_character.side_effect = Exception("err")
        daemon._personas = {"a": p}

        with patch("random.choices", return_value=["persona"]), \
             patch("random.choice") as mock_choice:
            # First choice call is _pick_next_speaker, second is seed fallback
            mock_choice.side_effect = [p, "What makes a good conversation?"]
            result = await daemon._generate_topic()
        assert isinstance(result, str)


class TestGenerateTopicGossip:
    """Covers lines 358-377: gossip topic."""
    @pytest.mark.asyncio
    async def test_gossip_success(self, daemon):
        daemon._read_public_chat = AsyncMock(return_value="User1: hey everyone!")
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="A gossip topic about humans")

        with patch("random.choices", return_value=["gossip"]):
            result = await daemon._generate_topic()
        assert result == "A gossip topic about humans"

    @pytest.mark.asyncio
    async def test_gossip_no_chat(self, daemon):
        daemon._read_public_chat = AsyncMock(return_value="")
        with patch("random.choices", return_value=["gossip"]):
            result = await daemon._generate_topic()
        assert isinstance(result, str)  # seed fallback

    @pytest.mark.asyncio
    async def test_gossip_exception(self, daemon):
        daemon._read_public_chat = AsyncMock(side_effect=Exception("err"))
        with patch("random.choices", return_value=["gossip"]):
            result = await daemon._generate_topic()
        assert isinstance(result, str)


class TestReadPublicChat:
    """Covers lines 392-412."""
    @pytest.mark.asyncio
    async def test_no_channel_id(self, daemon):
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 0
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            result = await daemon._read_public_chat()
        assert result == ""

    @pytest.mark.asyncio
    async def test_no_channel(self, daemon):
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345
        daemon.bot.get_channel.return_value = None
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            result = await daemon._read_public_chat()
        assert result == ""

    @pytest.mark.asyncio
    async def test_with_messages(self, daemon):
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345
        ch = MagicMock()
        m1 = MagicMock(); m1.author.bot = False; m1.content = "hello"; m1.author.display_name = "User1"
        m2 = MagicMock(); m2.author.bot = True; m2.content = "bot msg"; m2.author.display_name = "Bot"
        ch.history = MagicMock(return_value=AsyncIter([m1, m2]))
        daemon.bot.get_channel.return_value = ch
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            result = await daemon._read_public_chat()
        assert "User1: hello" in result
        assert "bot msg" not in result

    @pytest.mark.asyncio
    async def test_read_public_chat_exception(self, daemon):
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345
        daemon.bot.get_channel.side_effect = Exception("Channel Error")
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            result = await daemon._read_public_chat()
        assert result == ""


class TestStartLoop:
    """Covers lines 416-482: the daemon start loop."""
    @pytest.mark.asyncio
    async def test_already_running(self, daemon):
        daemon.is_running = True
        await daemon.start()  # Should return immediately
        assert True  # Execution completed without error

    @pytest.mark.asyncio
    async def test_one_iteration(self, daemon):
        call_count = 0
        async def mock_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                daemon.is_running = False
        
        p1 = MagicMock(); p1.name = "a"; p1.display_name = "A"; p1.record_message = Mock()
        p2 = MagicMock(); p2.name = "b"; p2.display_name = "B"; p2.record_message = Mock()
        daemon._personas = {"a": p1, "b": p2}
        daemon._generate_persona_response = AsyncMock(return_value="Test response")
        daemon._post_to_channel = AsyncMock()
        daemon._generate_topic = AsyncMock(return_value="Test topic")
        daemon._record_history = Mock()

        with patch("asyncio.sleep", side_effect=mock_sleep), \
             patch("random.randint", return_value=10), \
             patch("random.choice", return_value=p1):
            await daemon.start()
        assert daemon._conversation_turns >= 1

    @pytest.mark.asyncio
    async def test_too_few_personas(self, daemon):
        call_count = 0
        async def mock_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                daemon.is_running = False

        p1 = MagicMock(); p1.name = "a"
        daemon._personas = {"a": p1}  # Only 1 persona

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await daemon.start()
        assert True  # No exception: async operation completed within timeout

    @pytest.mark.asyncio
    async def test_fatal_error(self, daemon):
        async def mock_sleep(t):
            raise RuntimeError("fatal")

        p1 = MagicMock(); p1.name = "a"
        p2 = MagicMock(); p2.name = "b"
        daemon._personas = {"a": p1, "b": p2}

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await daemon.start()
        assert not daemon.is_running

    @pytest.mark.asyncio
    async def test_start_loop_cancelled(self, daemon):
        async def mock_sleep(t):
            import asyncio
            raise asyncio.CancelledError()

        p1 = MagicMock(); p1.name = "a"
        p2 = MagicMock(); p2.name = "b"
        daemon._personas = {"a": p1, "b": p2}

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await daemon.start()
        assert not daemon.is_running

    @pytest.mark.asyncio
    async def test_start_loop_missing_speaker_and_response(self, daemon):
        call_count = 0
        async def mock_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                daemon.is_running = False

        p1 = MagicMock(); p1.name = "a"
        p2 = MagicMock(); p2.name = "b"
        daemon._personas = {"a": p1, "b": p2}
        daemon._generate_topic = AsyncMock(return_value="Test topic")
        daemon._post_to_channel = AsyncMock()

        # Target line 201: if not speaker: continue
        with patch("asyncio.sleep", side_effect=mock_sleep), \
             patch("random.randint", return_value=12), \
             patch.object(daemon, "_pick_next_speaker", return_value=None):
            await daemon.start()

        call_count = 0
        daemon.is_running = False

        # Target line 205: if not response: continue
        daemon._generate_persona_response = AsyncMock(return_value=None)
        with patch("asyncio.sleep", side_effect=mock_sleep), \
             patch("random.randint", return_value=12), \
             patch.object(daemon, "_pick_next_speaker", return_value=p1):
            await daemon.start()


class TestGeneratePersonaResponse:
    """Covers lines 497-623: CognitionEngine pipeline path."""
    @pytest.mark.asyncio
    async def test_no_cognition_falls_back(self, daemon):
        daemon.bot.cognition = None
        daemon._topic = "test"
        sp = MagicMock(); sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "I am A."
        sp.get_context.return_value = []
        sp._home = MagicMock()
        with patch("src.daemons.town_hall_generation._generate_fallback", new_callable=AsyncMock, return_value="Fallback"):
            result = await daemon._generate_persona_response(sp)
        assert result == "Fallback"

    @pytest.mark.asyncio
    async def test_cognition_success(self, daemon):
        daemon._topic = "test"
        daemon.bot.cognition.process = AsyncMock(return_value=("Great response", [], []))
        daemon.bot.cognition.process = AsyncMock(return_value=("Great response", [], []))
        sp = MagicMock(); sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "I am a character with detailed personality."
        sp.get_context.return_value = [{"speaker": "b", "content": "hello"}]
        sp.get_opinions.return_value = {"AI": {"opinion": "fascinating"}}
        sp.get_relationships.return_value = {"b": {"sentiment": "friendly"}}
        sp.get_lessons.return_value = ["be kind"]
        sp._home = MagicMock()

        with patch("src.prompts.manager.PromptManager") as MockPM:
            pm = MagicMock()
            pm.get_system_prompt.return_value = "SYSTEM"
            MockPM.return_value = pm
            result = await daemon._generate_persona_response(sp)
        assert result == "Great response"

    @pytest.mark.asyncio
    async def test_cognition_strips_prefix(self, daemon):
        daemon._topic = "test"
        daemon.bot.cognition.process = AsyncMock(return_value=("Alice: stripped", [], []))
        daemon.bot.cognition.process = AsyncMock(return_value=("Alice: stripped", [], []))
        sp = MagicMock(); sp.name = "alice"; sp.display_name = "Alice"
        sp.get_character.return_value = "I am Alice."
        sp.get_context.return_value = []
        sp.get_opinions.return_value = {}
        sp.get_relationships.return_value = {}
        sp.get_lessons.return_value = []
        sp._home = MagicMock()

        with patch("src.prompts.manager.PromptManager") as MockPM:
            pm = MagicMock()
            pm.get_system_prompt.return_value = "S"
            MockPM.return_value = pm
            result = await daemon._generate_persona_response(sp)
        assert result == "stripped"

    @pytest.mark.asyncio
    async def test_cognition_exception_falls_back(self, daemon):
        daemon._topic = "test"
        daemon.bot.cognition.process = AsyncMock(side_effect=Exception("engine err"))
        daemon.bot.cognition.process = AsyncMock(side_effect=Exception("engine err"))
        sp = MagicMock(); sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "I am A."
        sp.get_context.return_value = []
        sp.get_opinions.return_value = {}
        sp.get_relationships.return_value = {}
        sp.get_lessons.return_value = []
        sp._home = MagicMock()

        with patch("src.prompts.manager.PromptManager") as MockPM, \
             patch("src.daemons.town_hall_generation._generate_fallback", new_callable=AsyncMock, return_value="Fallback OK"):
            pm = MagicMock()
            pm.get_system_prompt.return_value = "S"
            MockPM.return_value = pm
            result = await daemon._generate_persona_response(sp)
        assert result == "Fallback OK"

    @pytest.mark.asyncio
    async def test_cognition_returns_none(self, daemon):
        daemon._topic = "test"
        daemon.bot.cognition.process = AsyncMock(return_value=(None, [], []))
        daemon.bot.cognition.process = AsyncMock(return_value=(None, [], []))
        sp = MagicMock(); sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "I am A."
        sp.get_context.return_value = []
        sp.get_opinions.return_value = {}
        sp.get_relationships.return_value = {}
        sp.get_lessons.return_value = []
        sp._home = MagicMock()

        with patch("src.prompts.manager.PromptManager") as MockPM:
            pm = MagicMock(); pm.get_system_prompt.return_value = "S"
            MockPM.return_value = pm
            result = await daemon._generate_persona_response(sp)
        assert result is None


class TestPostToChannelEdgeCases:
    """Covers lines 673-675 (fetch fail), 689-692 (multi-chunk + exception)."""
    @pytest.mark.asyncio
    async def test_fetch_fails(self, daemon):
        mock_settings = MagicMock()
        mock_settings.PERSONA_CHAT_CHANNEL_ID = 12345
        daemon.bot.get_channel.return_value = None
        daemon.bot.fetch_channel = AsyncMock(side_effect=Exception("not found"))
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            await daemon._post_to_channel("A", "Hello")  # no raise
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_multi_chunk(self, daemon):
        mock_settings = MagicMock()
        mock_settings.PERSONA_CHAT_CHANNEL_ID = 12345
        ch = AsyncMock()
        daemon.bot.get_channel.return_value = ch
        long_text = "A" * 100 + ". " + "B" * 2100  # Will chunk
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await daemon._post_to_channel("A", long_text)
        assert ch.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_post_exception(self, daemon):
        mock_settings = MagicMock()
        mock_settings.PERSONA_CHAT_CHANNEL_ID = 12345
        ch = AsyncMock()
        ch.send.side_effect = Exception("discord error")
        daemon.bot.get_channel.return_value = ch
        with patch.dict("sys.modules", {"config.settings": mock_settings}), \
             patch("config.settings", mock_settings, create=True):
            await daemon._post_to_channel("A", "Hello")  # no raise
        assert True  # No exception: error handled gracefully


class TestFallbackWithContext:
    """Covers lines 632-655: fallback with conversation context."""
    @pytest.mark.asyncio
    async def test_with_history(self, daemon):
        daemon._topic = "test"
        daemon.bot.loop.run_in_executor = AsyncMock(return_value="response with context")
        sp = MagicMock(); sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "I am A."
        sp.get_context.return_value = [
            {"speaker": "b", "content": "hello"},
            {"speaker": "a", "content": "hi back"},
        ]
        result = await daemon._generate_persona_response_fallback(sp)
        assert result == "response with context"

    @pytest.mark.asyncio
    async def test_returns_none_response(self, daemon):
        daemon._topic = "test"
        daemon.bot.loop.run_in_executor = AsyncMock(return_value=None)
        sp = MagicMock(); sp.name = "a"; sp.display_name = "A"
        sp.get_character.return_value = "x"; sp.get_context.return_value = []
        assert await daemon._generate_persona_response_fallback(sp) is None

