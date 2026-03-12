"""
Unit tests for new file type support: EPUB, ODT, ODS, ODP, DOC, XLS, PPT.
Tests both the Discord attachment pipeline (chat_helpers.py) and the
filesystem tool pipeline (filesystem.py).
"""
import io
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock


# ── Chat Helpers (Discord Upload Pipeline) ─────────────────

class TestAttachmentProcessorNewFormats:
    """Test AttachmentProcessor.extract_text_from_bytes for new formats."""

    @pytest.fixture
    def processor(self):
        from src.bot.cogs.chat_helpers import AttachmentProcessor
        return AttachmentProcessor

    # ── EPUB ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_epub_extraction(self, processor):
        """Test EPUB extraction via ebooklib."""
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            pytest.skip("ebooklib not installed")

        # Create a minimal EPUB in memory
        book = epub.EpubBook()
        book.set_identifier("test123")
        book.set_title("Test Book")
        book.set_language("en")

        ch1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml")
        ch1.content = "<html><body><p>Hello from Chapter 1</p></body></html>"
        book.add_item(ch1)
        book.spine = ["nav", ch1]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Write to bytes
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            epub.write_epub(tmp.name, book)
            tmp.seek(0)
            epub_bytes = open(tmp.name, "rb").read()
            os.unlink(tmp.name)

        result = await processor.extract_text_from_bytes("test.epub", epub_bytes)
        assert "Hello from Chapter 1" in result

    @pytest.mark.asyncio
    async def test_epub_import_error(self, processor):
        """Test EPUB graceful fallback if ebooklib missing."""
        with patch.dict("sys.modules", {"ebooklib": None}):
            result = await processor.extract_text_from_bytes("test.epub", b"fake")
            assert "Error" in result

    # ── ODT ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_odt_extraction(self, processor):
        """Test ODT extraction via odfpy."""
        try:
            from odf.opendocument import OpenDocumentText
            from odf.text import P
            from odf import text as odf_text
        except ImportError:
            pytest.skip("odfpy not installed")

        doc = OpenDocumentText()
        p = P(text="Hello from ODT document")
        doc.text.addElement(p)

        with tempfile.NamedTemporaryFile(suffix=".odt", delete=False) as tmp:
            doc.save(tmp.name)
            odt_bytes = open(tmp.name, "rb").read()
            os.unlink(tmp.name)

        result = await processor.extract_text_from_bytes("test.odt", odt_bytes)
        assert "Hello from ODT" in result

    # ── ODS ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_ods_extraction(self, processor):
        """Test ODS extraction via odfpy."""
        try:
            from odf.opendocument import OpenDocumentSpreadsheet
            from odf.table import Table, TableRow, TableCell
            from odf.text import P
        except ImportError:
            pytest.skip("odfpy not installed")

        doc = OpenDocumentSpreadsheet()
        table = Table(name="Sheet1")
        row = TableRow()
        cell = TableCell()
        cell.addElement(P(text="A1"))
        row.addElement(cell)
        cell2 = TableCell()
        cell2.addElement(P(text="B1"))
        row.addElement(cell2)
        table.addElement(row)
        doc.spreadsheet.addElement(table)

        with tempfile.NamedTemporaryFile(suffix=".ods", delete=False) as tmp:
            doc.save(tmp.name)
            ods_bytes = open(tmp.name, "rb").read()
            os.unlink(tmp.name)

        result = await processor.extract_text_from_bytes("test.ods", ods_bytes)
        assert "A1" in result
        assert "B1" in result

    # ── ODP ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_odp_extraction(self, processor):
        """Test ODP extraction via odfpy."""
        try:
            from odf.opendocument import OpenDocumentPresentation
            from odf.draw import Page, Frame, TextBox
            from odf.text import P
            from odf.style import Style, MasterPage, PageLayout
        except ImportError:
            pytest.skip("odfpy not installed")

        doc = OpenDocumentPresentation()
        
        # ODP requires a page layout and master page
        pagelayout = PageLayout(name="MyLayout")
        doc.automaticstyles.addElement(pagelayout)
        masterpage = MasterPage(name="MyMaster", pagelayoutname=pagelayout)
        doc.masterstyles.addElement(masterpage)
        
        page = Page(name="Slide1", masterpagename=masterpage)
        frame = Frame()
        tb = TextBox()
        tb.addElement(P(text="Slide content here"))
        frame.addElement(tb)
        page.addElement(frame)
        doc.presentation.addElement(page)

        with tempfile.NamedTemporaryFile(suffix=".odp", delete=False) as tmp:
            doc.save(tmp.name)
            odp_bytes = open(tmp.name, "rb").read()
            os.unlink(tmp.name)

        result = await processor.extract_text_from_bytes("test.odp", odp_bytes)
        assert "Slide content here" in result

    # ── XLS ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_xls_extraction(self, processor):
        """Test XLS extraction via xlrd (mocked since xlrd can't write)."""
        mock_sheet = MagicMock()
        mock_sheet.name = "Sheet1"
        mock_sheet.nrows = 2
        mock_sheet.ncols = 2
        mock_sheet.cell_value.side_effect = lambda r, c: [["Name", "Age"], ["Alice", "30"]][r][c]

        mock_workbook = MagicMock()
        mock_workbook.sheets.return_value = [mock_sheet]

        with patch("xlrd.open_workbook", return_value=mock_workbook):
            result = await processor.extract_text_from_bytes("test.xls", b"fake xls")
            assert "Name" in result
            assert "Alice" in result

    # ── DOC ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_doc_extraction(self, processor):
        """Test DOC extraction via olefile (mocked)."""
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"Hello from legacy Word document"

        mock_ole = MagicMock()
        mock_ole.exists.return_value = True
        mock_ole.openstream.return_value = mock_stream

        with patch("olefile.OleFileIO", return_value=mock_ole):
            result = await processor.extract_text_from_bytes("test.doc", b"fake doc")
            assert "Hello from legacy Word document" in result

    # ── PPT ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_ppt_extraction(self, processor):
        """Test PPT extraction via olefile (mocked)."""
        # PPT stores text as UTF-16LE
        ppt_text = "Presentation slide text"
        mock_stream = MagicMock()
        mock_stream.read.return_value = ppt_text.encode("utf-16-le")

        mock_ole = MagicMock()
        mock_ole.exists.return_value = True
        mock_ole.openstream.return_value = mock_stream

        with patch("olefile.OleFileIO", return_value=mock_ole):
            result = await processor.extract_text_from_bytes("test.ppt", b"fake ppt")
            assert "Presentation slide text" in result


# ── Document Extensions Set ────────────────────────────────

class TestDocumentExtensions:
    """Verify that the _DOCUMENT_EXTENSIONS frozenset includes all new types."""

    def test_new_extensions_present(self):
        from src.bot.cogs.chat_attachments import _DOCUMENT_EXTENSIONS
        new_exts = [".epub", ".odt", ".ods", ".odp", ".doc", ".xls", ".ppt"]
        for ext in new_exts:
            assert ext in _DOCUMENT_EXTENSIONS, f"{ext} missing from _DOCUMENT_EXTENSIONS"


# ── Filesystem Tool ────────────────────────────────────────

class TestFilesystemNewFormats:
    """Test read_file_page for new formats via filesystem.py."""

    def test_epub_read(self):
        """Test EPUB reading from disk."""
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            pytest.skip("ebooklib not installed")

        book = epub.EpubBook()
        book.set_identifier("fs_test")
        book.set_title("FS Test")
        book.set_language("en")
        ch1 = epub.EpubHtml(title="Ch1", file_name="ch1.xhtml")
        ch1.content = "<html><body><p>Filesystem EPUB test</p></body></html>"
        book.add_item(ch1)
        book.spine = ["nav", ch1]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            epub.write_epub(tmp.name, book)
            path = tmp.name

        try:
            from src.tools.filesystem import read_file_page
            result = read_file_page(path)
            assert "Filesystem EPUB test" in result
        finally:
            os.unlink(path)

    def test_odt_read(self):
        """Test ODT reading from disk."""
        try:
            from odf.opendocument import OpenDocumentText
            from odf.text import P
        except ImportError:
            pytest.skip("odfpy not installed")

        doc = OpenDocumentText()
        doc.text.addElement(P(text="Filesystem ODT test"))

        with tempfile.NamedTemporaryFile(suffix=".odt", delete=False) as tmp:
            doc.save(tmp.name)
            path = tmp.name

        try:
            from src.tools.filesystem import read_file_page
            result = read_file_page(path)
            assert "Filesystem ODT test" in result
        finally:
            os.unlink(path)
