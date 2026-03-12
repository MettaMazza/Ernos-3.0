"""
Coverage tests for src/bot/cogs/chat_helpers.py.
Targets 91 uncovered lines across: AttachmentProcessor format handlers, ReactionHandler.
"""
import pytest
import io
from unittest.mock import patch, MagicMock, AsyncMock


class TestAttachmentProcessorPlainText:
    @pytest.mark.asyncio
    async def test_utf8(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        result = await AttachmentProcessor.extract_text_from_bytes("test.txt", b"Hello World")
        assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_latin1_fallback(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        # Bytes that aren't valid UTF-8 but valid Latin-1
        data = bytes([0xC0, 0xE0, 0xF0])
        result = await AttachmentProcessor.extract_text_from_bytes("test.txt", data)
        assert isinstance(result, str)



class TestAttachmentProcessorPDF:
    @pytest.mark.asyncio
    async def test_pdfplumber_success(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF content here"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)
        with patch.dict("sys.modules", {"pdfplumber": MagicMock()}):
            import sys
            sys.modules["pdfplumber"].open.return_value = mock_pdf
            result = await AttachmentProcessor.extract_text_from_bytes("doc.pdf", b"fake pdf")
        assert "PDF content" in result

    @pytest.mark.asyncio
    async def test_pdfplumber_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        # When pdfplumber raises ImportError, falls back to pypdf
        with patch.dict("sys.modules", {"pdfplumber": None}):
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "pypdf text"
            mock_reader.pages = [mock_page]
            with patch.dict("sys.modules", {"pypdf": MagicMock()}):
                import sys
                sys.modules["pypdf"].PdfReader.return_value = mock_reader
                result = await AttachmentProcessor.extract_text_from_bytes("doc.pdf", b"fake")
        assert "pypdf text" in result

    @pytest.mark.asyncio
    async def test_both_pdf_fail(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"pdfplumber": None, "pypdf": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("doc.pdf", b"fake")
        assert "Error" in result


class TestAttachmentProcessorDocx:
    @pytest.mark.asyncio
    async def test_docx_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"docx": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.docx", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_docx_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_docx = MagicMock()
        mock_docx.Document.side_effect = Exception("corrupt file")
        with patch.dict("sys.modules", {"docx": mock_docx}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.docx", b"bad")
        assert "Error" in result


class TestAttachmentProcessorPptx:
    @pytest.mark.asyncio
    async def test_pptx_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"pptx": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.pptx", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_pptx_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_pptx = MagicMock()
        mock_pptx.Presentation.side_effect = Exception("bad pptx")
        with patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.pptx", b"bad")
        assert "Error" in result


class TestAttachmentProcessorCSV:
    @pytest.mark.asyncio
    async def test_csv_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"pandas": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.csv", b"a,b\n1,2")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_csv_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_pd = MagicMock()
        mock_pd.read_csv.side_effect = Exception("bad csv")
        with patch.dict("sys.modules", {"pandas": mock_pd}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.csv", b"bad")
        assert "Error" in result


class TestAttachmentProcessorXlsx:
    @pytest.mark.asyncio
    async def test_xlsx_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"pandas": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.xlsx", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_xlsx_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_pd = MagicMock()
        mock_pd.ExcelFile.side_effect = Exception("bad xlsx")
        with patch.dict("sys.modules", {"pandas": mock_pd}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.xlsx", b"bad")
        assert "Error" in result


class TestAttachmentProcessorEpub:
    @pytest.mark.asyncio
    async def test_epub_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"ebooklib": None, "ebooklib.epub": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.epub", b"fake")
        assert "Error" in result




class TestAttachmentProcessorODT:
    @pytest.mark.asyncio
    async def test_odt_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"odf": None, "odf.opendocument": None, "odf.text": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.odt", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_odt_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_odf = MagicMock()
        mock_opendoc = MagicMock()
        mock_opendoc.load.side_effect = Exception("bad odt")
        with patch.dict("sys.modules", {"odf": mock_odf, "odf.opendocument": mock_opendoc, "odf.text": MagicMock()}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.odt", b"bad")
        assert "Error" in result


class TestAttachmentProcessorODS:
    @pytest.mark.asyncio
    async def test_ods_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"odf": None, "odf.opendocument": None, "odf.table": None, "odf.text": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.ods", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_ods_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_opendoc = MagicMock()
        mock_opendoc.load.side_effect = Exception("bad ods")
        with patch.dict("sys.modules", {"odf": MagicMock(), "odf.opendocument": mock_opendoc, "odf.table": MagicMock(), "odf.text": MagicMock()}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.ods", b"bad")
        assert "Error" in result


class TestAttachmentProcessorODP:
    @pytest.mark.asyncio
    async def test_odp_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"odf": None, "odf.opendocument": None, "odf.draw": None, "odf.text": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.odp", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_odp_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_opendoc = MagicMock()
        mock_opendoc.load.side_effect = Exception("bad odp")
        with patch.dict("sys.modules", {"odf": MagicMock(), "odf.opendocument": mock_opendoc, "odf.draw": MagicMock(), "odf.text": MagicMock()}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.odp", b"bad")
        assert "Error" in result


class TestAttachmentProcessorLegacyDoc:
    @pytest.mark.asyncio
    async def test_doc_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"olefile": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.doc", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_doc_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_ole = MagicMock()
        mock_ole.OleFileIO.side_effect = Exception("bad doc")
        with patch.dict("sys.modules", {"olefile": mock_ole}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.doc", b"bad")
        assert "Error" in result


class TestAttachmentProcessorLegacyXLS:
    @pytest.mark.asyncio
    async def test_xls_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"xlrd": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.xls", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_xls_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_xlrd = MagicMock()
        mock_xlrd.open_workbook.side_effect = Exception("bad xls")
        with patch.dict("sys.modules", {"xlrd": mock_xlrd}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.xls", b"bad")
        assert "Error" in result


class TestAttachmentProcessorLegacyPPT:
    @pytest.mark.asyncio
    async def test_ppt_not_installed(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        with patch.dict("sys.modules", {"olefile": None}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.ppt", b"fake")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_ppt_parse_error(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_ole = MagicMock()
        mock_ole.OleFileIO.side_effect = Exception("bad ppt")
        with patch.dict("sys.modules", {"olefile": mock_ole}):
            result = await AttachmentProcessor.extract_text_from_bytes("test.ppt", b"bad")
        assert "Error" in result


class TestAttachmentExtractText:
    @pytest.mark.asyncio
    async def test_delegates(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        mock_attachment = AsyncMock()
        mock_attachment.filename = "test.txt"
        mock_attachment.read.return_value = b"Hello"
        result = await AttachmentProcessor.extract_text(mock_attachment)
        assert result == "Hello"


class TestReactionHandler:
    @pytest.mark.asyncio
    async def test_self_reaction_ignored(self):
        from src.bot.cogs.chat_helpers import ReactionHandler
        bot = MagicMock()
        bot.user.id = 123
        handler = ReactionHandler(bot)
        payload = MagicMock()
        payload.user_id = 123  # Same as bot
        await handler.process_reaction(payload)  # Should return early, no crash

    @pytest.mark.asyncio
    async def test_silo_quorum(self):
        from src.bot.cogs.chat_helpers import ReactionHandler
        bot = MagicMock()
        bot.user.id = 123
        bot.silo_manager.check_quorum = AsyncMock()
        bot.cerebrum = None
        handler = ReactionHandler(bot)
        payload = MagicMock()
        payload.user_id = 456
        await handler.process_reaction(payload)
        bot.silo_manager.check_quorum.assert_awaited_once()
