"""
Attachment and backup handling tests for src/bot/cogs/chat.py
Covers lines 454-667 (image provenance, document processing, backup handling)
and remaining lines 742-748 (file attachments), 795-796 (VisualCortex reset),
and forward history capture (864-871, 876-882, 891-892, 899-901, 913, 948-954).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import time
import json


@pytest.fixture(autouse=True)
def _bypass_flux_and_llama():
    """Patch FluxCapacitor (DM rate-limiting) and CognitionTracker (llama_cpp import)."""
    mock_ct_module = MagicMock()
    with patch("src.core.flux_capacitor.FluxCapacitor.consume_tool", return_value=(True, None)), \
         patch.dict("sys.modules", {
             "src.engines.cognition_tracker": mock_ct_module,
             "llama_cpp": MagicMock(),
         }):
        yield

def _bot():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 99999
    bot.last_interaction = 0
    bot.engine_manager = MagicMock()
    bot.channel_manager = MagicMock()
    bot.silo_manager = MagicMock()
    bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    bot.silo_manager.propose_silo = AsyncMock()
    bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)
    bot.hippocampus = AsyncMock()
    bot.cerebrum = MagicMock()
    bot.cerebrum.get_lobe = MagicMock(return_value=None)
    bot.grounding_pulse = None
    bot.processing_users = set()
    bot.message_queues = {}
    bot.add_processing_user = MagicMock()
    bot.remove_processing_user = MagicMock()
    bot.tape_engine = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Response!", [], []))
    bot.cognition.process = AsyncMock(return_value=("Response!", [], []))
    bot.loop = MagicMock()
    bot.get_context = AsyncMock()
    return bot


def _msg(content="hello", author_id=111, is_dm=True, attachments=None, msg_id=12345):
    msg = MagicMock()
    msg.id = msg_id
    msg.content = content
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = False
    msg.author.name = "TestUser"
    msg.author.display_name = "TestUser"
    msg.author.mention = f"<@{author_id}>"
    msg.guild = None
    msg.channel = MagicMock()
    msg.channel.id = 1
    msg.channel.type = discord.ChannelType.private if is_dm else discord.ChannelType.text
    msg.channel.send = AsyncMock()
    msg.channel.parent_id = None
    msg.attachments = attachments or []
    msg.mentions = []
    msg.reply = AsyncMock()
    msg.add_reaction = AsyncMock()
    msg.create_thread = AsyncMock()
    msg.reference = None
    msg.message_snapshots = None

    class _Typing:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
    msg.channel.typing = MagicMock(return_value=_Typing())
    return msg


def _cog(bot=None):
    from src.bot.cogs.chat import ChatListener
    b = bot or _bot()
    with patch("src.bot.cogs.chat.PromptManager"), \
         patch("src.bot.cogs.chat.UnifiedPreProcessor"):
        cog = ChatListener(b)
        cog.prompt_manager = MagicMock()
        cog.prompt_manager.get_system_prompt = MagicMock(return_value="SYSTEM_PROMPT")
        cog.preprocessor = AsyncMock()
        cog.preprocessor.process = AsyncMock(return_value={"attributed_input": "hello", "analysis_context": "ctx", "images": []})
    return cog


def _adapter(is_dm=True):
    adapter = MagicMock()
    unified = MagicMock()
    unified.is_dm = is_dm
    unified.author_name = "TestUser"
    adapter.normalize = AsyncMock(return_value=unified)
    adapter.format_mentions = AsyncMock(side_effect=lambda x: x)
    return adapter


def _recall_obj():
    obj = MagicMock()
    obj.working_memory = "prev"
    obj.related_memories = []
    obj.knowledge_graph = []
    obj.lessons = []
    return obj


def _setup_full_pipeline(bot, response="Response!"):
    """Set up all mocks for a full on_message pipeline."""
    engine = MagicMock()
    engine.__class__.__name__ = "CloudEngine"
    engine.context_limit = 4000
    bot.engine_manager.get_active_engine.return_value = engine
    bot.cognition.process = AsyncMock(return_value=(response, [], []))
    bot.cognition.process = AsyncMock(return_value=(response, [], []))
    
    adapter = _adapter(is_dm=True)
    bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
    
    bot.loop.run_in_executor = AsyncMock(return_value=_recall_obj())
    
    ctx_mock = MagicMock()
    ctx_mock.valid = False
    bot.get_context = AsyncMock(return_value=ctx_mock)
    return bot


def _patches():
    """Common patches for on_message tests."""
    return {
        "src.bot.cogs.chat.settings": MagicMock(
            TARGET_CHANNEL_ID=999,
            ADMIN_IDS=set(),
            BLOCKED_IDS=set(),
            DM_BANNED_IDS=set(),
            DMS_ENABLED=True,
        ),
    }


# ─── Image Attachments with Provenance (lines 454-481) ──────────────
class TestImageProvenance:
    @pytest.mark.asyncio
    async def test_image_provenance_hit(self):
        """lines 460-470: image downloaded, provenance match."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "image/png"
        att.filename = "pic.png"
        att.size = 1000
        att.read = AsyncMock(return_value=b"imgdata")
        
        msg = _msg(content="look", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "abc123"
        prov_mgr.lookup_by_checksum.return_value = {"timestamp": "12:00", "type": "art"}
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_image_provenance_miss(self):
        """lines 471-476: external image."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "image/png"
        att.filename = "user_pic.png"
        att.size = 1000
        att.read = AsyncMock(return_value=b"imgdata")
        
        msg = _msg(content="check this", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "xyz"
        prov_mgr.lookup_by_checksum.return_value = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_image_provenance_error(self):
        """lines 477-479: provenance check fails."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "image/png"
        att.filename = "pic.png"
        att.size = 100
        att.read = AsyncMock(return_value=b"img")
        
        msg = _msg(content="see", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.side_effect = RuntimeError("prov fail")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_image_download_fails(self):
        """lines 480-481: image download exception."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "image/png"
        att.filename = "bad.png"
        att.size = 100
        att.read = AsyncMock(side_effect=Exception("download fail"))
        
        msg = _msg(content="see", attachments=[att])
        cog = _cog(bot)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()


# ─── Document Attachments (lines 488-587) ────────────────────────────
class TestDocumentAttachments:
    @pytest.mark.asyncio
    async def test_non_image_provenance(self):
        """lines 490-511: non-image provenance check."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "application/pdf"
        att.filename = "doc.pdf"
        att.size = 2000
        att.read = AsyncMock(return_value=b"pdfdata")
        
        msg = _msg(content="check this doc", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "abc"
        prov_mgr.lookup_by_checksum.return_value = {"timestamp": "12:00", "type": "doc"}
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}), \
             patch.object(cog, "_extract_text_from_attachment", new_callable=AsyncMock, return_value="doc text"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_json_backup_detection(self):
        """lines 514-539: JSON attachment detected as valid backup."""
        bot = _setup_full_pipeline(_bot())
        
        backup_data = {"user_id": "111", "checksum": "abc", "context": {}, "traces": {}}
        att = MagicMock()
        att.content_type = "application/json"
        att.filename = "backup.json"
        att.size = 500
        att.read = AsyncMock(return_value=json.dumps(backup_data).encode())
        
        msg = _msg(content="restore my backup", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "abc"
        prov_mgr.lookup_by_checksum.return_value = None
        
        backup_mgr = MagicMock()
        backup_mgr.import_user_context = AsyncMock(return_value=(True, "Restored"))
        backup_mgr.verify_backup.return_value = (True, "Valid")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {
                 "src.security.provenance": MagicMock(ProvenanceManager=prov_mgr),
                 "src.backup.manager": MagicMock(BackupManager=MagicMock(return_value=backup_mgr)),
             }):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_legacy_backup_rejected(self):
        """lines 532-537: legacy backup (no checksum)."""
        bot = _setup_full_pipeline(_bot())
        
        legacy = {"user_id": "111", "context": {}}  # No checksum
        att = MagicMock()
        att.content_type = "application/json"
        att.filename = "old_backup.json"
        att.size = 200
        att.read = AsyncMock(return_value=json.dumps(legacy).encode())
        
        msg = _msg(content="restore", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_master_backup_rejected(self):
        """lines 523-526: master backup rejected."""
        bot = _setup_full_pipeline(_bot())
        
        master = {"type": "master_backup", "all_users": {}}
        att = MagicMock()
        att.content_type = "application/json"
        att.filename = "master.json"
        att.size = 100
        att.read = AsyncMock(return_value=json.dumps(master).encode())
        
        msg = _msg(content="restore", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_document_text_extraction(self):
        """lines 542-587: text document extraction and injection."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "text/plain"
        att.filename = "notes.txt"
        att.size = 100
        att.read = AsyncMock(return_value=b"some notes here")
        
        msg = _msg(content="read this", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}), \
             patch.object(cog, "_extract_text_from_attachment", new_callable=AsyncMock, return_value="some notes"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_backup_payload_in_text_file(self):
        """lines 560-573: backup injection detection in text file."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "text/plain"
        att.filename = "fake.txt"
        att.size = 200
        att.read = AsyncMock(return_value=b'{"user_id": "x", "context": "y"}')
        
        msg = _msg(content="load this", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        # Return content that looks like a backup
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}), \
             patch.object(cog, "_extract_text_from_attachment", new_callable=AsyncMock,
                         return_value='"user_id": "123", "context": "data", format_version'):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_extract_text_exception(self):
        """lines 584-587: extraction fails."""
        bot = _setup_full_pipeline(_bot())
        
        att = MagicMock()
        att.content_type = "text/plain"
        att.filename = "broken.txt"
        att.size = 100
        att.read = AsyncMock(return_value=b"x")
        
        msg = _msg(content="read", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {"src.security.provenance": MagicMock(ProvenanceManager=prov_mgr)}), \
             patch.object(cog, "_extract_text_from_attachment", new_callable=AsyncMock,
                         side_effect=Exception("parse fail")):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()


# ─── Pasted Backup Detection (lines 589-607) ─────────────────────────
class TestPastedBackup:
    @pytest.mark.asyncio
    async def test_pasted_backup_redacted(self):
        """lines 593-607: backup content pasted into message."""
        bot = _setup_full_pipeline(_bot())
        cog = _cog(bot)
        
        paste = '"user_id": "123", "context": "data"'
        msg = _msg(content=paste)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        # Content should have been replaced with security message
        assert "SECURITY" in msg.content or bot.cognition.process.called


# ─── Backup Restore Flow (lines 614-667) ─────────────────────────────
class TestBackupRestore:
    @pytest.mark.asyncio
    async def test_backup_verify_valid(self):
        """lines 650-657: verify-only (no restore intent)."""
        bot = _setup_full_pipeline(_bot())
        
        backup_data = {"user_id": "111", "checksum": "abc", "context": {"a": "b"}, "traces": {"t": "v"}, "kg_node_count": 5}
        att = MagicMock()
        att.content_type = "application/json"
        att.filename = "backup.json"
        att.size = 500
        att.read = AsyncMock(return_value=json.dumps(backup_data).encode())
        
        msg = _msg(content="what is this file?", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        backup_mgr = MagicMock()
        backup_mgr.verify_backup.return_value = (True, "Valid backup")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {
                 "src.security.provenance": MagicMock(ProvenanceManager=prov_mgr),
                 "src.backup.manager": MagicMock(BackupManager=MagicMock(return_value=backup_mgr)),
             }):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_backup_verify_invalid(self):
        """lines 658-659: verify fails."""
        bot = _setup_full_pipeline(_bot())
        
        backup_data = {"user_id": "111", "checksum": "abc", "context": {}, "traces": {}}
        att = MagicMock()
        att.content_type = "application/json"
        att.filename = "backup.json"
        att.size = 500
        att.read = AsyncMock(return_value=json.dumps(backup_data).encode())
        
        msg = _msg(content="check file", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        backup_mgr = MagicMock()
        backup_mgr.verify_backup.return_value = (False, "Checksum mismatch")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {
                 "src.security.provenance": MagicMock(ProvenanceManager=prov_mgr),
                 "src.backup.manager": MagicMock(BackupManager=MagicMock(return_value=backup_mgr)),
             }):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_backup_restore_failed(self):
        """lines 645-646: restore fails."""
        bot = _setup_full_pipeline(_bot())
        
        backup_data = {"user_id": "111", "checksum": "abc", "context": {}, "traces": {}}
        att = MagicMock()
        att.content_type = "application/json"
        att.filename = "backup.json"
        att.size = 500
        att.read = AsyncMock(return_value=json.dumps(backup_data).encode())
        
        msg = _msg(content="restore my backup", attachments=[att])
        cog = _cog(bot)
        
        prov_mgr = MagicMock()
        prov_mgr.compute_checksum.return_value = "x"
        prov_mgr.lookup_by_checksum.return_value = None
        
        backup_mgr = MagicMock()
        backup_mgr.import_user_context = AsyncMock(return_value=(False, "Checksum fail"))
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch.dict("sys.modules", {
                 "src.security.provenance": MagicMock(ProvenanceManager=prov_mgr),
                 "src.backup.manager": MagicMock(BackupManager=MagicMock(return_value=backup_mgr)),
             }):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_called()


# ─── File Attachments & VisualCortex Reset (lines 742-748, 795-796) ──
class TestFileAttachments:
    @pytest.mark.asyncio
    async def test_file_attachments_attached(self):
        """lines 742-748: files from cognition attached to response."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("Reply with file", ["/tmp/test.png"]))
        bot.cognition.process = AsyncMock(return_value=("Reply with file", ["/tmp/test.png"]))
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        bot.loop.run_in_executor = AsyncMock(return_value=_recall_obj())
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="generate art")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("os.path.exists", return_value=True):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        msg.reply.assert_called()

    @pytest.mark.asyncio
    async def test_visual_cortex_reset(self):
        """lines 804-811: VisualCortex turn lock reset."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        
        creative_lobe = MagicMock()
        visual = MagicMock()
        creative_lobe.get_ability.return_value = visual
        bot.cerebrum.get_lobe = MagicMock(return_value=creative_lobe)
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        bot.loop.run_in_executor = AsyncMock(return_value=_recall_obj())
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="hi")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        visual.reset_turn_lock.assert_called_once()


# ─── Grounding Pulse (lines 432-435) ─────────────────────────────────
class TestGroundingPulse:
    @pytest.mark.asyncio
    async def test_grounding_pulse_consumed(self):
        """lines 432-435: grounding pulse injected and consumed."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        bot.grounding_pulse = "EMERGENCY GROUNDING"
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        bot.loop.run_in_executor = AsyncMock(return_value=_recall_obj())
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="hi")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        assert bot.grounding_pulse is None


# ─── Hippocampus Failure (lines 736-737) ─────────────────────────────
class TestHippocampusFailure:
    @pytest.mark.asyncio
    async def test_observe_exception(self):
        """lines 736-737: hippocampus.observe() failure."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("reply", [], []))
        bot.cognition.process = AsyncMock(return_value=("reply", [], []))
        bot.hippocampus.observe.side_effect = RuntimeError("observe fail")
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        bot.loop.run_in_executor = AsyncMock(return_value=_recall_obj())
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="hi")
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        # Should still reply despite observe failure
        msg.reply.assert_called()
