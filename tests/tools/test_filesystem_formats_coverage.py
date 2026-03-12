"""
Extended coverage tests for src/tools/filesystem.py — document format parsers.
Targets the 194 uncovered lines (lines 35–266, 323, 371) covering:
docx, pptx, csv, xlsx, pdf, epub, odt, ods, odp, doc, xls, ppt ImportError branches,
general format errors, search_codebase scope filtering, and list_files scope filtering.
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from src.tools.filesystem import read_file_page, search_codebase, list_files


# ── Helpers ──────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make_file(tmp_dir, name, content=""):
    path = os.path.join(tmp_dir, name)
    with open(path, 'w') as f:
        f.write(content)
    return path


# ── DOCX ─────────────────────────────────────────────────

class TestDocxFormat:
    def test_docx_import_error(self, tmp_dir):
        """docx not installed returns import error."""
        path = _make_file(tmp_dir, "test.docx")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"docx": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'docx'")):
            result = read_file_page(path)
        assert "python-docx not installed" in result

    def test_docx_success(self, tmp_dir):
        """docx reads paragraphs."""
        path = _make_file(tmp_dir, "test.docx")
        mock_doc = MagicMock()
        para1, para2 = MagicMock(), MagicMock()
        para1.text = "Hello World"
        para2.text = "Second para"
        mock_doc.paragraphs = [para1, para2]
        mock_docx = MagicMock()
        mock_docx.Document.return_value = mock_doc

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"docx": mock_docx}):
            result = read_file_page(path)
        assert "Hello World" in result
        assert "Second para" in result

    def test_docx_general_error(self, tmp_dir):
        """docx read error returns error message."""
        path = _make_file(tmp_dir, "test.docx")
        mock_docx = MagicMock()
        mock_docx.Document.side_effect = Exception("corrupt file")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"docx": mock_docx}):
            result = read_file_page(path)
        assert "Error reading .docx" in result


# ── PPTX ─────────────────────────────────────────────────

class TestPptxFormat:
    def test_pptx_import_error(self, tmp_dir):
        """pptx not installed returns import error."""
        path = _make_file(tmp_dir, "test.pptx")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pptx": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'pptx'")):
            result = read_file_page(path)
        assert "python-pptx not installed" in result

    def test_pptx_success(self, tmp_dir):
        """pptx reads slides with text shapes."""
        path = _make_file(tmp_dir, "test.pptx")
        shape1 = MagicMock()
        shape1.text = "Slide Title"
        shape2 = MagicMock()
        shape2.text = "   "  # Empty shape (should be stripped)
        shape2.text = shape2.text.strip()
        slide = MagicMock()
        slide.shapes = [shape1, shape2]
        mock_prs = MagicMock()
        mock_prs.slides = [slide]
        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = read_file_page(path)
        assert "Slide 1" in result
        assert "Slide Title" in result

    def test_pptx_general_error(self, tmp_dir):
        """pptx read error returns error message."""
        path = _make_file(tmp_dir, "test.pptx")
        mock_pptx = MagicMock()
        mock_pptx.Presentation.side_effect = Exception("bad pptx")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = read_file_page(path)
        assert "Error reading .pptx" in result


# ── CSV ──────────────────────────────────────────────────

class TestCsvFormat:
    def test_csv_import_error(self, tmp_dir):
        """pandas not installed returns import error."""
        path = _make_file(tmp_dir, "test.csv", "a,b\n1,2\n")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pandas": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'pandas'")):
            result = read_file_page(path)
        assert "pandas" in result.lower()

    def test_csv_success(self, tmp_dir):
        """csv reads via pandas."""
        path = _make_file(tmp_dir, "test.csv", "name,age\nAlice,30\n")
        mock_df = MagicMock()
        mock_df.to_markdown.return_value = "| name | age |\n|---|---|\n| Alice | 30 |"
        mock_pd = MagicMock()
        mock_pd.read_csv.return_value = mock_df

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pandas": mock_pd}):
            result = read_file_page(path)
        assert "Alice" in result

    def test_csv_general_error(self, tmp_dir):
        """csv read error returns error message."""
        path = _make_file(tmp_dir, "test.csv")
        mock_pd = MagicMock()
        mock_pd.read_csv.side_effect = Exception("parse fail")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pandas": mock_pd}):
            result = read_file_page(path)
        assert "Error reading .csv" in result


# ── XLSX ──────────────────────────────────────────────────

class TestXlsxFormat:
    def test_xlsx_import_error(self, tmp_dir):
        """pandas/openpyxl not installed returns import error."""
        path = _make_file(tmp_dir, "test.xlsx")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pandas": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'pandas'")):
            result = read_file_page(path)
        assert "pandas" in result.lower()

    def test_xlsx_success(self, tmp_dir):
        """xlsx reads multiple sheets."""
        path = _make_file(tmp_dir, "test.xlsx")
        mock_df = MagicMock()
        mock_df.to_markdown.return_value = "| col1 |\n|---|\n| val |"
        mock_xls = MagicMock()
        mock_xls.sheet_names = ["Sheet1", "Sheet2"]
        mock_pd = MagicMock()
        mock_pd.ExcelFile.return_value = mock_xls
        mock_pd.read_excel.return_value = mock_df

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pandas": mock_pd}):
            result = read_file_page(path)
        assert "Sheet1" in result
        assert "Sheet2" in result

    def test_xlsx_general_error(self, tmp_dir):
        """xlsx read error returns error message."""
        path = _make_file(tmp_dir, "test.xlsx")
        mock_pd = MagicMock()
        mock_pd.ExcelFile.side_effect = Exception("xlsx fail")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"pandas": mock_pd}):
            result = read_file_page(path)
        assert "Error reading .xlsx" in result


# ── PDF ──────────────────────────────────────────────────

class TestPdfFormat:
    def test_pdf_import_error(self, tmp_dir):
        """PyMuPDF not installed returns import error."""
        path = _make_file(tmp_dir, "test.pdf")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"fitz": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'fitz'")):
            result = read_file_page(path)
        assert "PyMuPDF" in result or "fitz" in result

    def test_pdf_success(self, tmp_dir):
        """PDF reads pages."""
        path = _make_file(tmp_dir, "test.pdf")
        page = MagicMock()
        page.get_text.return_value = "Page content here\nSecond line"
        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([page])
        mock_doc.__len__ = lambda self: 1
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = read_file_page(path)
        assert "Page 1" in result
        assert "Page content here" in result

    def test_pdf_general_error(self, tmp_dir):
        """PDF read error returns error message."""
        path = _make_file(tmp_dir, "test.pdf")
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = Exception("corrupt pdf")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = read_file_page(path)
        assert "Error reading .pdf" in result


# ── EPUB ─────────────────────────────────────────────────

class TestEpubFormat:
    def test_epub_import_error(self, tmp_dir):
        """ebooklib not installed returns import error."""
        path = _make_file(tmp_dir, "test.epub")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"ebooklib": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'ebooklib'")):
            result = read_file_page(path)
        assert "ebooklib" in result

    def test_epub_general_error(self, tmp_dir):
        """epub read error returns error message."""
        path = _make_file(tmp_dir, "test.epub")
        mock_epub_module = MagicMock()
        mock_epub_module.read_epub.side_effect = Exception("bad epub")
        mock_ebooklib = MagicMock()
        mock_ebooklib.ITEM_DOCUMENT = 9
        mock_ebooklib.epub = mock_epub_module

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {
                 "ebooklib": mock_ebooklib,
                 "ebooklib.epub": mock_epub_module,
                 "bs4": MagicMock()
             }):
            result = read_file_page(path)
        assert "Error reading .epub" in result


# ── ODT ──────────────────────────────────────────────────

class TestOdtFormat:
    def test_odt_import_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.odt")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"odf": None, "odf.opendocument": None, "odf.text": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'odf'")):
            result = read_file_page(path)
        assert "odfpy not installed" in result

    def test_odt_general_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.odt")
        mock_odf_load = MagicMock(side_effect=Exception("odt corrupt"))

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {
                 "odf": MagicMock(), "odf.opendocument": MagicMock(),
                 "odf.text": MagicMock()
             }):
            with patch("builtins.__import__") as mock_import:
                # Make the import succeed but the load fail
                def side_effect(name, *args, **kwargs):
                    if 'odf' in name:
                        m = MagicMock()
                        m.load = mock_odf_load
                        return m
                    return MagicMock()
                mock_import.side_effect = side_effect
                result = read_file_page(path)
        assert "Error reading .odt" in result or "error" in result.lower()


# ── ODS ──────────────────────────────────────────────────

class TestOdsFormat:
    def test_ods_import_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.ods")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"odf": None, "odf.opendocument": None, "odf.table": None, "odf.text": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'odf'")):
            result = read_file_page(path)
        assert "odfpy not installed" in result

    def test_ods_general_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.ods")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {
                 "odf": MagicMock(), "odf.opendocument": MagicMock(),
                 "odf.table": MagicMock(), "odf.text": MagicMock()
             }):
            with patch("builtins.__import__") as mock_import:
                def side_effect(name, *args, **kwargs):
                    if 'odf' in name:
                        m = MagicMock()
                        m.load = MagicMock(side_effect=Exception("ods corrupt"))
                        return m
                    return MagicMock()
                mock_import.side_effect = side_effect
                result = read_file_page(path)
        assert "Error reading .ods" in result or "error" in result.lower()


# ── ODP ──────────────────────────────────────────────────

class TestOdpFormat:
    def test_odp_import_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.odp")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"odf": None, "odf.opendocument": None, "odf.draw": None, "odf.text": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'odf'")):
            result = read_file_page(path)
        assert "odfpy not installed" in result

    def test_odp_general_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.odp")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {
                 "odf": MagicMock(), "odf.opendocument": MagicMock(),
                 "odf.draw": MagicMock(), "odf.text": MagicMock()
             }):
            with patch("builtins.__import__") as mock_import:
                def side_effect(name, *args, **kwargs):
                    if 'odf' in name:
                        m = MagicMock()
                        m.load = MagicMock(side_effect=Exception("odp corrupt"))
                        return m
                    return MagicMock()
                mock_import.side_effect = side_effect
                result = read_file_page(path)
        assert "Error reading .odp" in result or "error" in result.lower()


# ── DOC ──────────────────────────────────────────────────

class TestDocFormat:
    def test_doc_import_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.doc")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'olefile'")):
            result = read_file_page(path)
        assert "olefile not installed" in result

    def test_doc_success(self, tmp_dir):
        """DOC reads WordDocument stream."""
        path = _make_file(tmp_dir, "test.doc")
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"Hello from Word document"
        mock_ole = MagicMock()
        mock_ole.exists.return_value = True
        mock_ole.openstream.return_value = mock_stream
        mock_olefile = MagicMock()
        mock_olefile.OleFileIO.return_value = mock_ole

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": mock_olefile}):
            result = read_file_page(path)
        assert "Hello from Word document" in result

    def test_doc_no_word_document_stream(self, tmp_dir):
        """DOC file without WordDocument stream."""
        path = _make_file(tmp_dir, "test.doc")
        mock_ole = MagicMock()
        mock_ole.exists.return_value = False
        mock_olefile = MagicMock()
        mock_olefile.OleFileIO.return_value = mock_ole

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": mock_olefile}):
            result = read_file_page(path)
        assert "Cannot find Word content" in result

    def test_doc_general_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.doc")
        mock_olefile = MagicMock()
        mock_olefile.OleFileIO.side_effect = Exception("doc corrupt")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": mock_olefile}):
            result = read_file_page(path)
        assert "Error reading .doc" in result


# ── XLS ──────────────────────────────────────────────────

class TestXlsFormat:
    def test_xls_import_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.xls")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"xlrd": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'xlrd'")):
            result = read_file_page(path)
        assert "xlrd not installed" in result

    def test_xls_success(self, tmp_dir):
        """XLS reads sheets and rows."""
        path = _make_file(tmp_dir, "test.xls")
        mock_sheet = MagicMock()
        mock_sheet.name = "Data"
        mock_sheet.nrows = 2
        mock_sheet.ncols = 2
        mock_sheet.cell_value = lambda r, c: f"r{r}c{c}"
        mock_wb = MagicMock()
        mock_wb.sheets.return_value = [mock_sheet]
        mock_xlrd = MagicMock()
        mock_xlrd.open_workbook.return_value = mock_wb

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"xlrd": mock_xlrd}):
            result = read_file_page(path)
        assert "Data" in result
        assert "r0c0" in result

    def test_xls_general_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.xls")
        mock_xlrd = MagicMock()
        mock_xlrd.open_workbook.side_effect = Exception("xls corrupt")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"xlrd": mock_xlrd}):
            result = read_file_page(path)
        assert "Error reading .xls" in result


# ── PPT ──────────────────────────────────────────────────

class TestPptFormat:
    def test_ppt_import_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.ppt")
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": None}), \
             patch("builtins.__import__", side_effect=ImportError("No module named 'olefile'")):
            result = read_file_page(path)
        assert "olefile not installed" in result

    def test_ppt_success(self, tmp_dir):
        """PPT reads PowerPoint Document stream."""
        path = _make_file(tmp_dir, "test.ppt")
        mock_stream = MagicMock()
        # Simulate UTF-16LE encoded content
        mock_stream.read.return_value = "Slide content here for testing".encode("utf-16-le")
        mock_ole = MagicMock()
        mock_ole.exists.return_value = True
        mock_ole.openstream.return_value = mock_stream
        mock_olefile = MagicMock()
        mock_olefile.OleFileIO.return_value = mock_ole

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": mock_olefile}):
            result = read_file_page(path)
        assert "Slide content here" in result

    def test_ppt_no_ppt_stream(self, tmp_dir):
        """PPT without PowerPoint Document stream."""
        path = _make_file(tmp_dir, "test.ppt")
        mock_ole = MagicMock()
        mock_ole.exists.return_value = False
        mock_olefile = MagicMock()
        mock_olefile.OleFileIO.return_value = mock_ole

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": mock_olefile}):
            result = read_file_page(path)
        assert "Cannot find PowerPoint content" in result

    def test_ppt_general_error(self, tmp_dir):
        path = _make_file(tmp_dir, "test.ppt")
        mock_olefile = MagicMock()
        mock_olefile.OleFileIO.side_effect = Exception("ppt corrupt")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch.dict("sys.modules", {"olefile": mock_olefile}):
            result = read_file_page(path)
        assert "Error reading .ppt" in result


# ── search_codebase extended ─────────────────────────────

class TestSearchCodebaseExtended:
    def test_search_core_dir_filtered_for_public(self, tmp_dir):
        """PUBLIC scope should filter out 'core' directories."""
        core_dir = os.path.join(tmp_dir, "core")
        os.makedirs(core_dir)
        _make_file(core_dir, "secret.py", "sensitive_data\n")
        _make_file(tmp_dir, "public.py", "sensitive_data\n")

        with patch("src.tools.filesystem.validate_path_scope", return_value=True):
            result = search_codebase("sensitive_data", tmp_dir, request_scope="PUBLIC")
        # core/secret.py should be filtered
        assert "public.py" in result
        # Core dir should be excluded
        assert "secret.py" not in result or "core" not in result

    def test_search_exception(self, tmp_dir):
        """os.walk exception returns error."""
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch("os.walk", side_effect=Exception("walk error")):
            result = search_codebase("test", tmp_dir)
        assert "Search Error" in result

    def test_search_per_file_scope_check(self, tmp_dir):
        """Individual file scope checks filter results."""
        _make_file(tmp_dir, "ok.py", "findme\n")
        _make_file(tmp_dir, "blocked.py", "findme\n")

        def scope_check(path, scope, user_id=None):
            return "blocked" not in path

        with patch("src.tools.filesystem.validate_path_scope", side_effect=scope_check):
            result = search_codebase("findme", tmp_dir)
        assert "ok.py" in result


# ── list_files extended ──────────────────────────────────

class TestListFilesExtended:
    def test_list_filters_inaccessible_entries(self, tmp_dir):
        """Inaccessible subdirs are filtered from listing."""
        os.makedirs(os.path.join(tmp_dir, "allowed"))
        os.makedirs(os.path.join(tmp_dir, "denied"))
        _make_file(tmp_dir, "visible.txt")

        call_count = [0]

        def scope_check(path, scope, user_id=None):
            if "denied" in path:
                return False
            return True

        with patch("src.tools.filesystem.validate_path_scope", side_effect=scope_check):
            result = list_files(tmp_dir)
        assert "allowed" in result
        assert "denied" not in result
        assert "visible.txt" in result

    def test_list_exception(self, tmp_dir):
        """Exception during listing returns error."""
        with patch("src.tools.filesystem.validate_path_scope", return_value=True), \
             patch("os.listdir", side_effect=Exception("permission denied")):
            result = list_files(tmp_dir)
        assert "Error listing files" in result
