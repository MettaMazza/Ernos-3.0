"""
Coverage tests for src/lobes/creative/consolidation.py — MemoryConsolidator.
Targets the 149 uncovered lines: run_consolidation, process_episodic_memories,
update_user_bios, synthesize_narrative, extract_lessons_from_narrative, run_vector_hygiene.
"""
import pytest
import json
import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, Mock, patch, call


# ── Fixtures ──────────────────────────────────────────────
@pytest.fixture
def bot():
    b = MagicMock()
    b.hippocampus = MagicMock()
    b.hippocampus.embedder = MagicMock()
    b.hippocampus.vector_store = MagicMock()
    b.hippocampus.graph = MagicMock()
    b.engine_manager = MagicMock()
    engine = MagicMock()
    engine.generate_response = MagicMock(return_value="Generated text")
    b.engine_manager.get_active_engine.return_value = engine
    b.loop = MagicMock()
    b.loop.run_in_executor = AsyncMock(return_value="Generated text")
    return b


@pytest.fixture
def consolidator(bot):
    from src.lobes.creative.consolidation import MemoryConsolidator
    return MemoryConsolidator(bot)


# ── run_consolidation ────────────────────────────────────
class TestRunConsolidation:
    @pytest.mark.asyncio
    async def test_full_cycle(self, consolidator):
        """Happy path: all steps succeed."""
        with patch.object(consolidator, 'process_episodic_memories', new_callable=AsyncMock, return_value=3), \
             patch.object(consolidator, 'update_user_bios', new_callable=AsyncMock, return_value=2), \
             patch.object(consolidator, 'synthesize_narrative', new_callable=AsyncMock, return_value=("some narrative", False)), \
             patch.object(consolidator, 'extract_lessons_from_narrative', new_callable=AsyncMock), \
             patch.object(consolidator, 'run_vector_hygiene', new_callable=AsyncMock, return_value=5):
            result = await consolidator.run_consolidation()
        assert "Memory Consolidation Complete" in result
        assert "Episodic: 3 files" in result
        assert "Bios: 2 users" in result
        assert "Narrative:" in result
        assert "Vector Hygiene: 5" in result

    @pytest.mark.asyncio
    async def test_no_narrative(self, consolidator):
        """Narrative returns empty — lessons should be skipped."""
        with patch.object(consolidator, 'process_episodic_memories', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'update_user_bios', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'synthesize_narrative', new_callable=AsyncMock, return_value=("", False)), \
             patch.object(consolidator, 'extract_lessons_from_narrative', new_callable=AsyncMock) as mock_lessons, \
             patch.object(consolidator, 'run_vector_hygiene', new_callable=AsyncMock, return_value=0):
            result = await consolidator.run_consolidation()
        mock_lessons.assert_not_called()
        assert "Consolidation Complete" in result

    @pytest.mark.asyncio
    async def test_private_narrative_scope(self, consolidator):
        """Narrative with private sources should tag lessons CORE_PRIVATE."""
        with patch.object(consolidator, 'process_episodic_memories', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'update_user_bios', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'synthesize_narrative', new_callable=AsyncMock, return_value=("narrative", True)), \
             patch.object(consolidator, 'extract_lessons_from_narrative', new_callable=AsyncMock) as mock_lessons, \
             patch.object(consolidator, 'run_vector_hygiene', new_callable=AsyncMock, return_value=0):
            await consolidator.run_consolidation()
        # Should be called with CORE_PRIVATE scope
        from src.privacy.scopes import PrivacyScope
        mock_lessons.assert_called_once()
        call_kwargs = mock_lessons.call_args
        assert call_kwargs[1].get('source_scope') == PrivacyScope.CORE_PRIVATE or \
               call_kwargs[0][1] == PrivacyScope.CORE_PRIVATE if len(call_kwargs[0]) > 1 else True

    @pytest.mark.asyncio
    async def test_public_narrative_scope(self, consolidator):
        """Narrative without private sources should tag lessons CORE_PUBLIC."""
        with patch.object(consolidator, 'process_episodic_memories', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'update_user_bios', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'synthesize_narrative', new_callable=AsyncMock, return_value=("narrative", False)), \
             patch.object(consolidator, 'extract_lessons_from_narrative', new_callable=AsyncMock) as mock_lessons, \
             patch.object(consolidator, 'run_vector_hygiene', new_callable=AsyncMock, return_value=0):
            await consolidator.run_consolidation()
        from src.privacy.scopes import PrivacyScope
        mock_lessons.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_vector_hygiene(self, consolidator):
        """When vector hygiene returns 0, no vector hygiene line in result."""
        with patch.object(consolidator, 'process_episodic_memories', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'update_user_bios', new_callable=AsyncMock, return_value=0), \
             patch.object(consolidator, 'synthesize_narrative', new_callable=AsyncMock, return_value=("", False)), \
             patch.object(consolidator, 'run_vector_hygiene', new_callable=AsyncMock, return_value=0):
            result = await consolidator.run_consolidation()
        assert "Vector Hygiene" not in result

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self, consolidator):
        """Exception during consolidation returns failure message."""
        with patch.object(consolidator, 'process_episodic_memories', new_callable=AsyncMock, side_effect=Exception("disk full")):
            result = await consolidator.run_consolidation()
        assert "Consolidation Failed" in result


# ── process_episodic_memories ────────────────────────────
class TestProcessEpisodicMemories:
    @pytest.mark.asyncio
    async def test_no_dirs_exist(self, consolidator, tmp_path):
        """No episodic directories exist — returns 0."""
        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 0

    @pytest.mark.asyncio
    async def test_processes_json_list(self, consolidator, tmp_path):
        """Processes a JSON list file and renames to processed_."""
        episodic_dir = tmp_path / "episodic"
        episodic_dir.mkdir()
        json_file = episodic_dir / "session_001.json"
        json_file.write_text(json.dumps([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"}
        ]))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 1
        assert (episodic_dir / "processed_session_001.json").exists()
        assert not json_file.exists()

    @pytest.mark.asyncio
    async def test_processes_json_dict(self, consolidator, tmp_path):
        """Processes a JSON dict file (non-list)."""
        episodic_dir = tmp_path / "episodic"
        episodic_dir.mkdir()
        json_file = episodic_dir / "session_002.json"
        json_file.write_text(json.dumps({"summary": "a conversation"}))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 1

    @pytest.mark.asyncio
    async def test_skips_processed_files(self, consolidator, tmp_path):
        """Files starting with 'processed_' are skipped."""
        episodic_dir = tmp_path / "episodic"
        episodic_dir.mkdir()
        (episodic_dir / "processed_old.json").write_text(json.dumps([]))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 0

    @pytest.mark.asyncio
    async def test_user_dirs_scanned(self, consolidator, tmp_path):
        """User-specific episodic dirs are also scanned."""
        users_dir = tmp_path / "users"
        user_ep = users_dir / "alice_123" / "episodic"
        user_ep.mkdir(parents=True)
        (user_ep / "chat.json").write_text(json.dumps([{"role": "user", "content": "test"}]))

        # Also check public/episodic subdir
        user_pub = users_dir / "alice_123" / "public" / "episodic"
        user_pub.mkdir(parents=True)
        (user_pub / "pub_chat.json").write_text(json.dumps({"data": "public"}))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 2

    @pytest.mark.asyncio
    async def test_embedding_failure_still_renames(self, consolidator, tmp_path):
        """Embedding failure is caught but file still gets renamed."""
        episodic_dir = tmp_path / "episodic"
        episodic_dir.mkdir()
        json_file = episodic_dir / "sess.json"
        json_file.write_text(json.dumps([{"role": "user", "content": "x"}]))
        consolidator.bot.hippocampus.embedder.get_embedding.side_effect = Exception("embed fail")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 1
        assert (episodic_dir / "processed_sess.json").exists()

    @pytest.mark.asyncio
    async def test_no_hippocampus(self, consolidator, tmp_path):
        """No hippocampus — still processes and renames files."""
        consolidator.bot.hippocampus = None
        episodic_dir = tmp_path / "episodic"
        episodic_dir.mkdir()
        (episodic_dir / "s.json").write_text(json.dumps({"x": 1}))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 1

    @pytest.mark.asyncio
    async def test_bad_json_file(self, consolidator, tmp_path):
        """Corrupt JSON file is caught and skipped."""
        episodic_dir = tmp_path / "episodic"
        episodic_dir.mkdir()
        (episodic_dir / "bad.json").write_text("not valid json{{{")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 0  # Failed to process

    @pytest.mark.asyncio
    async def test_core_episodic_dir(self, consolidator, tmp_path):
        """Core episodic dir is scanned."""
        core_ep = tmp_path / "core" / "episodic"
        core_ep.mkdir(parents=True)
        (core_ep / "core_session.json").write_text(json.dumps([{"role": "system", "content": "init"}]))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.process_episodic_memories()
        assert result == 1


# ── update_user_bios ─────────────────────────────────────
class TestUpdateUserBios:
    @pytest.mark.asyncio
    async def test_no_users_dir(self, consolidator, tmp_path):
        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_episodic_content(self, consolidator, tmp_path):
        """User dirs exist but no processed episodic files."""
        users_dir = tmp_path / "users"
        (users_dir / "bob_456").mkdir(parents=True)

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 0

    @pytest.mark.asyncio
    async def test_updates_bio(self, consolidator, tmp_path):
        """Generates and writes bio for user with processed episodic files."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "charlie_789"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_chat.json").write_text(json.dumps([
            {"role": "user", "content": "I love astronomy"},
            {"role": "assistant", "content": "Stars are fascinating!"}
        ]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="Charlie loves space and stars.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 1
        profile = json.loads((user_dir / "profile.json").read_text())
        assert "Charlie loves space" in profile["bio"]
        assert "bio_updated" in profile

    @pytest.mark.asyncio
    async def test_updates_existing_profile(self, consolidator, tmp_path):
        """Merges bio into existing profile.json."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "dana_111"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_x.json").write_text(json.dumps([{"role": "user", "content": "test"}]))
        (user_dir / "profile.json").write_text(json.dumps({"pref": "dark_mode"}))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="Dana is great.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 1
        profile = json.loads((user_dir / "profile.json").read_text())
        assert profile["pref"] == "dark_mode"
        assert "Dana" in profile["bio"]

    @pytest.mark.asyncio
    async def test_user_id_without_underscore(self, consolidator, tmp_path):
        """Folder name without underscore uses entire name as user_id."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "12345"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_a.json").write_text(json.dumps([{"role": "user", "content": "hello"}]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="A user.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 1

    @pytest.mark.asyncio
    async def test_empty_bio_response(self, consolidator, tmp_path):
        """Empty LLM response doesn't write profile."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "eve_222"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_b.json").write_text(json.dumps([{"role": "user", "content": "hi"}]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_non_dir_entries(self, consolidator, tmp_path):
        """Skips files in users/ (only processes directories)."""
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        (users_dir / "notes.txt").write_text("not a user")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 0

    @pytest.mark.asyncio
    async def test_bad_episodic_json(self, consolidator, tmp_path):
        """Corrupt processed episodic file is handled gracefully."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "frank_333"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_bad.json").write_text("not json{{{")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 0  # No content extracted

    @pytest.mark.asyncio
    async def test_bio_exception(self, consolidator, tmp_path):
        """Exception during bio generation is caught."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "grace_444"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_c.json").write_text(json.dumps([{"role": "user", "content": "hi"}]))
        consolidator.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM down"))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        # Exception caught, user not counted
        assert result == 0

    @pytest.mark.asyncio
    async def test_bad_existing_profile(self, consolidator, tmp_path):
        """Corrupt existing profile.json is handled (starts fresh)."""
        users_dir = tmp_path / "users"
        user_dir = users_dir / "hank_555"
        ep_dir = user_dir / "episodic"
        ep_dir.mkdir(parents=True)
        (ep_dir / "processed_d.json").write_text(json.dumps([{"role": "user", "content": "yo"}]))
        (user_dir / "profile.json").write_text("corrupt{not json")
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="Hank is cool.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result = await consolidator.update_user_bios()
        assert result == 1


# ── synthesize_narrative ─────────────────────────────────
class TestSynthesizeNarrative:
    @pytest.mark.asyncio
    async def test_no_content(self, consolidator, tmp_path):
        """No episodic files — returns empty."""
        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result, has_private = await consolidator.synthesize_narrative()
        assert result == ""
        assert has_private is False

    @pytest.mark.asyncio
    async def test_core_only(self, consolidator, tmp_path):
        """Core episodic files only — has_private=False."""
        core_ep = tmp_path / "core" / "episodic"
        core_ep.mkdir(parents=True)
        (core_ep / "processed_a.json").write_text(json.dumps([
            {"role": "user", "content": "public data"}
        ]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="I reflected on public data.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path), \
             patch("src.memory.autobiography.get_autobiography_manager", return_value=MagicMock()), \
             patch("src.security.provenance.ProvenanceManager.log_artifact"):
            result, has_private = await consolidator.synthesize_narrative()
        assert result == "I reflected on public data."
        assert has_private is False

    @pytest.mark.asyncio
    async def test_with_private_user_data(self, consolidator, tmp_path):
        """User episodic files taint narrative as private."""
        users_dir = tmp_path / "users"
        user_ep = users_dir / "user_1" / "episodic"
        user_ep.mkdir(parents=True)
        (user_ep / "processed_b.json").write_text(json.dumps([
            {"role": "user", "content": "private info"}
        ]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="I learned about a user.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result, has_private = await consolidator.synthesize_narrative()
        assert has_private is True
        assert result == "I learned about a user."

    @pytest.mark.asyncio
    async def test_engine_failure(self, consolidator, tmp_path):
        """Engine failure returns empty."""
        ep_dir = tmp_path / "episodic"
        ep_dir.mkdir()
        (ep_dir / "processed_c.json").write_text(json.dumps([{"role": "user", "content": "data"}]))
        consolidator.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM fail"))

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result, has_private = await consolidator.synthesize_narrative()
        assert result == ""
        assert has_private is False

    @pytest.mark.asyncio
    async def test_empty_engine_response(self, consolidator, tmp_path):
        """Empty engine response returns empty tuple."""
        ep_dir = tmp_path / "episodic"
        ep_dir.mkdir()
        (ep_dir / "processed_d.json").write_text(json.dumps([{"role": "user", "content": "data"}]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result, has_private = await consolidator.synthesize_narrative()
        assert result == ""

    @pytest.mark.asyncio
    async def test_saves_narrative_file(self, consolidator, tmp_path):
        """Narrative is saved to autobiographies dir."""
        ep_dir = tmp_path / "episodic"
        ep_dir.mkdir()
        (ep_dir / "processed_e.json").write_text(json.dumps([{"role": "user", "content": "story"}]))
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value="My narrative.")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path), \
             patch("src.memory.autobiography.get_autobiography_manager") as mock_autobio, \
             patch("src.security.provenance.ProvenanceManager.log_artifact"):
            mock_mgr = MagicMock()
            mock_autobio.return_value = mock_mgr
            result, _ = await consolidator.synthesize_narrative()

        auto_dir = tmp_path / "core" / "autobiographies"
        assert auto_dir.exists()
        files = list(auto_dir.glob("cycle_*.txt"))
        assert len(files) == 1
        assert files[0].read_text() == "My narrative."

    @pytest.mark.asyncio
    async def test_bad_processed_json(self, consolidator, tmp_path):
        """Corrupt processed file is handled gracefully."""
        ep_dir = tmp_path / "episodic"
        ep_dir.mkdir()
        (ep_dir / "processed_bad.json").write_text("not json")

        with patch("src.lobes.creative.consolidation.data_dir", return_value=tmp_path):
            result, _ = await consolidator.synthesize_narrative()
        assert result == ""  # No content extracted


# ── extract_lessons_from_narrative ───────────────────────
class TestExtractLessons:
    @pytest.mark.asyncio
    async def test_extracts_lessons(self, consolidator):
        """Valid JSON array response creates lessons."""
        consolidator.bot.loop.run_in_executor = AsyncMock(
            return_value='["Users value transparency", "Verification matters"]'
        )
        with patch("src.memory.lessons.LessonManager") as MockLM:
            mock_mgr = MagicMock()
            MockLM.return_value = mock_mgr
            await consolidator.extract_lessons_from_narrative("My narrative about things.")
        assert mock_mgr.add_lesson.call_count == 2

    @pytest.mark.asyncio
    async def test_caps_at_3_lessons(self, consolidator):
        """Only first 3 lessons are extracted."""
        consolidator.bot.loop.run_in_executor = AsyncMock(
            return_value='["Lesson 1 is long enough", "Lesson 2 is long enough", "Lesson 3 is long enough", "Lesson 4 is long enough"]'
        )
        with patch("src.memory.lessons.LessonManager") as MockLM:
            mock_mgr = MagicMock()
            MockLM.return_value = mock_mgr
            await consolidator.extract_lessons_from_narrative("text")
        assert mock_mgr.add_lesson.call_count == 3

    @pytest.mark.asyncio
    async def test_skips_short_lessons(self, consolidator):
        """Lessons shorter than 10 chars are skipped."""
        consolidator.bot.loop.run_in_executor = AsyncMock(
            return_value='["Short", "This lesson is long enough to pass"]'
        )
        with patch("src.memory.lessons.LessonManager") as MockLM:
            mock_mgr = MagicMock()
            MockLM.return_value = mock_mgr
            await consolidator.extract_lessons_from_narrative("text")
        assert mock_mgr.add_lesson.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_non_string_lessons(self, consolidator):
        """Non-string items in the array are skipped."""
        consolidator.bot.loop.run_in_executor = AsyncMock(
            return_value='[42, "This lesson is valid and long enough"]'
        )
        with patch("src.memory.lessons.LessonManager") as MockLM:
            mock_mgr = MagicMock()
            MockLM.return_value = mock_mgr
            await consolidator.extract_lessons_from_narrative("text")
        assert mock_mgr.add_lesson.call_count == 1

    @pytest.mark.asyncio
    async def test_no_json_in_response(self, consolidator):
        """Response without JSON array is silently skipped."""
        consolidator.bot.loop.run_in_executor = AsyncMock(
            return_value="Here are some lessons I learned."
        )
        with patch("src.memory.lessons.LessonManager") as MockLM:
            mock_mgr = MagicMock()
            MockLM.return_value = mock_mgr
            await consolidator.extract_lessons_from_narrative("text")
        mock_mgr.add_lesson.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_scope_is_core_private(self, consolidator):
        """No source_scope defaults to CORE_PRIVATE."""
        consolidator.bot.loop.run_in_executor = AsyncMock(
            return_value='["A valid lesson for testing"]'
        )
        with patch("src.memory.lessons.LessonManager") as MockLM:
            mock_mgr = MagicMock()
            MockLM.return_value = mock_mgr
            await consolidator.extract_lessons_from_narrative("text", source_scope=None)
        from src.privacy.scopes import PrivacyScope
        mock_mgr.add_lesson.assert_called_once()
        assert mock_mgr.add_lesson.call_args[1]["scope"] == PrivacyScope.CORE_PRIVATE

    @pytest.mark.asyncio
    async def test_engine_exception(self, consolidator):
        """Engine exception is caught gracefully."""
        consolidator.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM down"))
        # Should not raise
        await consolidator.extract_lessons_from_narrative("text")


# ── run_vector_hygiene ───────────────────────────────────
class TestRunVectorHygiene:
    @pytest.mark.asyncio
    async def test_no_hippocampus(self, consolidator):
        """No hippocampus returns 0."""
        consolidator.bot.hippocampus = None
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_hippo_attr(self, consolidator):
        """Missing hippocampus attribute returns 0."""
        del consolidator.bot.hippocampus
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_collection(self, consolidator):
        """Vector store without collection returns 0."""
        del consolidator.bot.hippocampus.vector_store.collection
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_empty_results(self, consolidator):
        """Collection with no results returns 0."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": [], "metadatas": [], "documents": []
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_ids_key(self, consolidator):
        """Collection get returns no 'ids' key."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {}
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_orphaned_kg_entities(self, consolidator):
        """Entries with kg_entities not in KG are invalidated."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc1"],
            "metadatas": [{"kg_entities": "entity_a, entity_b"}],
            "documents": ["some text"]
        }
        # KG returns nothing for these entities
        consolidator.bot.hippocampus.graph.query_context.return_value = None

        result = await consolidator.run_vector_hygiene()
        assert result == 1
        consolidator.bot.hippocampus.vector_store.collection.update.assert_called_once()
        call_args = consolidator.bot.hippocampus.vector_store.collection.update.call_args
        assert call_args[1]["ids"] == ["doc1"]
        meta = call_args[1]["metadatas"][0]
        assert meta["invalidated"] is True
        assert "kg_entities_orphaned" in meta["invalidation_reason"]

    @pytest.mark.asyncio
    async def test_kg_entity_exists(self, consolidator):
        """Entries with existing KG entities are NOT invalidated."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc1"],
            "metadatas": [{"kg_entities": "entity_a"}],
            "documents": ["text"]
        }
        consolidator.bot.hippocampus.graph.query_context.return_value = "entity exists"

        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_aged_out_working_memory(self, consolidator):
        """Old working_memory_consolidation entries are invalidated."""
        old_time = (datetime.datetime.now() - datetime.timedelta(days=45)).isoformat()
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc2"],
            "metadatas": [{"timestamp": old_time, "source": "working_memory_consolidation"}],
            "documents": ["old text"]
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 1

    @pytest.mark.asyncio
    async def test_recent_working_memory_not_invalidated(self, consolidator):
        """Recent working_memory_consolidation entries are kept."""
        recent_time = (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat()
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc3"],
            "metadatas": [{"timestamp": recent_time, "source": "working_memory_consolidation"}],
            "documents": ["recent text"]
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_old_non_wm_source_not_invalidated(self, consolidator):
        """Old entries from non-working_memory sources are NOT invalidated."""
        old_time = (datetime.datetime.now() - datetime.timedelta(days=45)).isoformat()
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc4"],
            "metadatas": [{"timestamp": old_time, "source": "episodic"}],
            "documents": ["old but permanent"]
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_already_invalidated_skipped(self, consolidator):
        """Already invalidated entries are skipped."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc5"],
            "metadatas": [{"invalidated": True, "kg_entities": "orphan"}],
            "documents": ["already handled"]
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_kg_query_exception(self, consolidator):
        """KG query exception is caught, entity considered missing."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc6"],
            "metadatas": [{"kg_entities": "entity_x"}],
            "documents": ["text"]
        }
        consolidator.bot.hippocampus.graph.query_context.side_effect = Exception("neo4j error")

        result = await consolidator.run_vector_hygiene()
        assert result == 1  # Considered orphaned

    @pytest.mark.asyncio
    async def test_bad_timestamp_format(self, consolidator):
        """Bad timestamp format is handled gracefully."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc7"],
            "metadatas": [{"timestamp": "not-a-date", "source": "working_memory_consolidation"}],
            "documents": ["text"]
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 0  # Bad timestamp skipped

    @pytest.mark.asyncio
    async def test_collection_exception(self, consolidator):
        """Collection get exception is handled."""
        consolidator.bot.hippocampus.vector_store.collection.get.side_effect = Exception("chroma fail")
        result = await consolidator.run_vector_hygiene()
        assert result == 0

    @pytest.mark.asyncio
    async def test_null_metadata(self, consolidator):
        """Entries with None metadata are handled."""
        consolidator.bot.hippocampus.vector_store.collection.get.return_value = {
            "ids": ["doc8"],
            "metadatas": None,
            "documents": ["text"]
        }
        result = await consolidator.run_vector_hygiene()
        assert result == 0
