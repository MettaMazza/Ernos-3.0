import pytest
import asyncio
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from src.tools.document import (
    _get_draft_path, _resolve_doc_id, _load_draft, _save_draft,
    _markdown_to_html, _looks_like_html, _looks_like_markdown,
    _build_styled_html, _image_to_base64,
    generate_pdf, start_document, add_section, embed_image,
    edit_section, remove_section, update_document, render_document,
    DRAFTS_DIR, THEME_OVERRIDES
)

class TestDocumentBaseUtils:
    @patch("src.tools.document.Path")
    @patch("src.tools.document.os.path.exists")
    def test_get_draft_path(self, mock_exists, mock_path):
        # Even though Path is mocked, typically it returns a mock object.
        # It's better to just call the real logic but we can mock DRAFTS_DIR if needed.
        # But _get_draft_path uses DRAFTS_DIR.
        mock_p = MagicMock()
        with patch("src.tools.document.DRAFTS_DIR", mock_p):
            _get_draft_path("doc123")
            mock_p.__truediv__.assert_called_with("doc123.json")

    @patch("src.tools.document._get_draft_path")
    @patch("src.tools.document.DRAFTS_DIR")
    def test_resolve_doc_id(self, mock_drafts_dir, mock_get_draft):
        mock_path = MagicMock()
        mock_get_draft.return_value = mock_path
        
        # Exact match
        mock_path.exists.return_value = True
        assert _resolve_doc_id("test") == "test"
        
        # Fallback mode
        mock_path.exists.return_value = False
        mock_drafts_dir.exists.return_value = True
        
        # Create some mock files
        f1 = MagicMock()
        f1.stem = "doc_1"
        f1.stat().st_mtime = 100
        f2 = MagicMock()
        f2.stem = "doc_2"
        f2.stat().st_mtime = 200
        
        mock_drafts_dir.glob.return_value = [f2, f1] # returning in sorted order to simulate finding doc 2 first
        
        assert _resolve_doc_id("test") == "doc_2"
        
        # Fallback empty
        mock_drafts_dir.glob.return_value = []
        with pytest.raises(FileNotFoundError):
            _resolve_doc_id("test")

    @patch("src.tools.document._get_draft_path")
    def test_load_draft(self, mock_get_draft):
        mock_path = MagicMock()
        mock_get_draft.return_value = mock_path
        
        mock_path.exists.return_value = False
        with pytest.raises(FileNotFoundError):
            _load_draft("test")
        
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"title": "test"}'
        assert _load_draft("test") == {"title": "test"}

    @patch("src.tools.document._get_draft_path")
    @patch("src.tools.document.DRAFTS_DIR")
    def test_save_draft(self, mock_drafts_dir, mock_get_draft):
        mock_path = MagicMock()
        mock_get_draft.return_value = mock_path
        _save_draft("test", {"title": "test"})
        mock_drafts_dir.mkdir.assert_called_with(parents=True, exist_ok=True)
        assert mock_path.write_text.called

    def test_markdown_to_html(self):
        html = _markdown_to_html("# Hello\n**Bold**")
        assert ">Hello</h1>" in html
        assert "<strong>Bold</strong>" in html
        
        # Error fallback
        with patch.dict("sys.modules", {"markdown": None}):
            res = _markdown_to_html("Test")
            assert "<p>Test</p>" == res
            
    def test_looks_like_html(self):
        assert _looks_like_html("<p>hello</p>")
        assert not _looks_like_html("> blockquote")
        
    def test_looks_like_markdown(self):
        assert _looks_like_markdown("# Header\n- list\n**bold**")
        assert not _looks_like_markdown("Just normal text")
        
    def test_build_styled_html(self):
        html = _build_styled_html("<p>Test</p>", theme="dark", title="My Title", custom_css="body { color: red; }")
        assert "<p>Test</p>" in html
        assert THEME_OVERRIDES["dark"] in html
        assert "My Title" in html
        assert "body { color: red; }" in html
        
    @patch("src.tools.document.Path")
    def test_image_to_base64_success(self, mock_path):
        mock_p = MagicMock()
        mock_path.return_value = mock_p
        mock_p.exists.return_value = True
        mock_p.read_bytes.return_value = b"image_data"
        mock_p.suffix = ".png"
        
        b64 = _image_to_base64("test.png")
        assert b64 == f"data:image/png;base64,{base64.b64encode(b'image_data').decode()}"
        
    @patch("src.tools.document.Path")
    def test_image_to_base64_not_found(self, mock_path):
        mock_p = MagicMock()
        mock_path.return_value = mock_p
        mock_p.exists.return_value = False
        mock_p.__truediv__.return_value.exists.return_value = False
        with pytest.raises(FileNotFoundError):
            _image_to_base64("bad.png")
        
    @patch("src.tools.document.Path")
    def test_image_to_base64_error(self, mock_path):
        mock_p = MagicMock()
        mock_path.return_value = mock_p
        mock_p.exists.return_value = True
        mock_p.suffix = ".png"
        mock_p.read_bytes.side_effect = Exception("Read error")
        with pytest.raises(Exception):
            _image_to_base64("bad.png")

class TestDocumentComposition:
    @patch("src.tools.document._save_draft")
    def test_start_document(self, mock_save):
        res = start_document("My Title", author="Me", theme="dark", custom_css="css")
        assert "SUCCESS: Document created:" in res
        assert "doc_" in res
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        data = args[1]
        assert data["title"] == "My Title"
        assert data["author"] == "Me"
        assert data["theme"] == "dark"
        assert data["custom_css"] == "css"
        assert data["sections"] == []
        
    @patch("src.tools.document._save_draft")
    def test_start_document_error(self, mock_save):
        mock_save.side_effect = Exception("Save error")
        with pytest.raises(Exception, match="Save error"):
            start_document("My Title")

    @patch("src.tools.document._load_draft")
    @patch("src.tools.document._save_draft")
    @patch("src.tools.document._resolve_doc_id")
    def test_add_section(self, mock_resolve, mock_save, mock_load):
        mock_resolve.return_value = "doc1"
        mock_load.return_value = {"sections": []}
        
        res = add_section("doc1", "Header", "Content", "markdown")
        assert "SUCCESS: Section 1 added" in res
        args, _ = mock_save.call_args
        assert args[1]["sections"][0]["heading"] == "Header"
        assert args[1]["sections"][0]["content_type"] == "markdown"
        
        # Not found
        mock_load.side_effect = FileNotFoundError("Missing")
        res = add_section("doc1", "Header", "Content")
        assert "Missing" in res
        
        # Error
        mock_load.side_effect = Exception("Err")
        with pytest.raises(Exception, match="Err"):
            add_section("doc1", "Header", "Content")

    @patch("src.tools.document._load_draft")
    @patch("src.tools.document._save_draft")
    @patch("src.tools.document._resolve_doc_id")
    @patch("src.tools.document._image_to_base64")
    def test_embed_image(self, mock_b64, mock_resolve, mock_save, mock_load):
        mock_resolve.return_value = "doc1"
        mock_load.return_value = {"sections": [{"type": "text", "html": "hello", "heading": "h1", "images": []}]}
        mock_b64.return_value = "data:image/png;base64,123"
        
        # Success append to specific section
        res = embed_image("doc1", "img.png", width="50%", section_index=0)
        assert "Image embedded" in res
        args, _ = mock_save.call_args
        sec_imgs = args[1]["sections"][0]["images"]
        assert len(sec_imgs) == 1
        assert sec_imgs[0]["data_uri"] == "data:image/png;base64,123"
        
        # Error b64
        mock_b64.side_effect = FileNotFoundError("Missing")
        res = embed_image("doc1", "img.png")
        assert "Missing" in res
        
        # Out of bounds
        mock_b64.return_value = "data"
        res = embed_image("doc1", "img.png", section_index=5)
        assert "Error: Invalid section_index 5" in res
        
    @patch("src.tools.document._load_draft")
    @patch("src.tools.document._save_draft")
    @patch("src.tools.document._resolve_doc_id")
    def test_edit_section(self, mock_resolve, mock_save, mock_load):
        mock_resolve.return_value = "doc1"
        mock_load.return_value = {"sections": [{"heading": "Old", "html": "Text", "type": "markdown", "images": []}]}
        
        res = edit_section("doc1", 0, heading="New", content="New Text")
        assert "SUCCESS" in res
        args, _ = mock_save.call_args
        assert args[1]["sections"][0]["heading"] == "New"
        assert ">New Text</h1>" in args[1]["sections"][0]["html"] or "<p>New Text</p>" in args[1]["sections"][0]["html"]
        
        # Bad index
        res = edit_section("doc1", 5, heading="New")
        assert "Error: Invalid section_index 5" in res

    @patch("src.tools.document._load_draft")
    @patch("src.tools.document._save_draft")
    @patch("src.tools.document._resolve_doc_id")
    def test_remove_section(self, mock_resolve, mock_save, mock_load):
        mock_resolve.return_value = "doc1"
        mock_load.return_value = {"sections": [{"heading": "Old", "html": "Text", "type": "markdown", "images": []}]}
        
        res = remove_section("doc1", 0)
        assert "SUCCESS" in res
        assert len(mock_save.call_args[0][1]["sections"]) == 0
        
        res = remove_section("doc1", 5)
        assert "Error: Invalid section_index 5" in res

    @patch("src.tools.document._load_draft")
    @patch("src.tools.document._save_draft")
    @patch("src.tools.document._resolve_doc_id")
    def test_update_document(self, mock_resolve, mock_save, mock_load):
        mock_resolve.return_value = "doc1"
        mock_load.return_value = {"title": "Old", "author": "A", "theme": "A", "custom_css": "A"}
        
        res = update_document("doc1", title="New", author="B", theme="B", custom_css="B")
        assert "SUCCESS" in res
        data = mock_save.call_args[0][1]
        assert data["title"] == "New"
        assert data["author"] == "B"
        assert data["theme"] == "B"
        assert data["custom_css"] == "B"

    @pytest.mark.asyncio
    @patch("playwright.async_api.async_playwright")
    @patch("src.tools.document.Path")
    @patch("src.security.provenance.ProvenanceManager.log_artifact")
    async def test_generate_pdf_coverage_gaps(self, mock_log, mock_path, mock_pw):
        from src.tools.document import generate_pdf
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_pw.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        mock_path_obj = MagicMock()
        mock_path_obj.__truediv__.return_value = mock_path_obj
        mock_path_obj.exists.return_value = True
        mock_path.return_value = mock_path_obj
        
        # Hit request_scope="INVALID" exception (lines 514-516)
        res1 = await generate_pdf("target text", request_scope="INVALID")
        assert "✅ SUCCESS" in res1
        
        # Hit is_html and not is_md branch (lines 550-551)
        res2 = await generate_pdf("<h1>Pure HTML</h1><p>No markdown here</p>")
        assert "✅ SUCCESS" in res2
        
        # Hit is_md branch (lines 554-555)
        res3 = await generate_pdf("# Markdown\n* list")
        assert "✅ SUCCESS" in res3

    @pytest.mark.asyncio
    @patch("src.tools.document._load_draft")
    @patch("src.tools.document._resolve_doc_id")
    @patch("src.tools.document._save_draft")
    @patch("playwright.async_api.async_playwright")
    @patch("src.security.provenance.ProvenanceManager.log_artifact")
    async def test_render_document(self, mock_prov, mock_pw, mock_save, mock_resolve, mock_load):
        # The main wrapper
        from src.tools.document import render_document
        mock_resolve.return_value = "doc1"
        mock_load.return_value = {
            "title": "Title",
            "author": "Aut",
            "theme": "dark",
            "custom_css": "",
            "sections": [
                {
                    "heading": "H", 
                    "html": "hello", 
                    "type": "markdown", 
                    "images": [{"data_uri": "data:image/png;base64,...", "width": "100%", "caption": "A test image!"}]
                }
            ]
        }
        
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_pw.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        res = await render_document("doc1")
        assert "SUCCESS" in res
        mock_page.pdf.assert_called_once()
        
        # Test not found
        mock_load.side_effect = FileNotFoundError("Missing")
        res = await render_document("doc1")
        assert "Missing" in res
        
        # Test empty sections (line 947)
        mock_load.side_effect = None
        mock_load.return_value = {"sections": []}
        res_empty = await render_document("doc1")
        assert "has no sections" in res_empty
        
        # Test already rendered (lines 951-952)
        mock_load.return_value = {"status": "rendered", "title": "A", "author": "B", "theme": "dark", "custom_css": "", "sections": [{"html": "hi", "heading": "h1", "images": []}]}
        res_rendered = await render_document("doc1")
        assert "ALREADY RENDERED" in res_rendered
        
        # But works if force=True
        res_force = await render_document("doc1", force=True)
        assert "SUCCESS" in res_force
        
        # Test generation error
        mock_load.side_effect = None
        mock_load.return_value = {"title": "Title", "author": "Aut", "theme": "dark", "custom_css": "", "sections": [{"heading": "H", "html": "hello", "type": "markdown"}]}
        mock_pw.side_effect = Exception("Browser failed to launch")
        res = await render_document("doc1")
        assert "Render Error" in res
        
    @pytest.mark.asyncio
    @patch("playwright.async_api.async_playwright")
    async def test_generate_pdf_exceptions(self, mock_pw):
        # We handle exceptions gracefully inside generate_pdf
        from src.tools.document import generate_pdf
        
        mock_pw.side_effect = Exception("Browser failed to launch")
        res = await generate_pdf("target text")
        assert "PDF Error" in res
        assert "Browser failed to launch" in res
        
        # Check specific playwright timeout
        from playwright.async_api import TimeoutError
        mock_pw.side_effect = TimeoutError("Navigation timeout")
        res = await generate_pdf("target text")
        assert "PDF Error" in res


class TestListImages:
    def test_list_images_empty(self, tmp_path):
        from src.tools.document import list_images
        with patch("src.tools.document.os.getcwd", return_value=str(tmp_path)):
            res = list_images()
            assert "No images found" in res

    def test_list_images_success(self, tmp_path):
        from src.tools.document import list_images
        
        # Create a matching path for media
        media_dir = tmp_path / "memory" / "core" / "media"
        media_dir.mkdir(parents=True)
        img_file = media_dir / "test1.png"
        img_file.write_bytes(b"fake image data")
        
        # Create user paths to hit lines 1094-1102
        user_media = tmp_path / "memory" / "users" / "user123" / "media"
        user_media.mkdir(parents=True)
        user_img = user_media / "auto_test2.jpg"
        user_img.write_bytes(b"fake bytes")
        
        # Test nested core media in user dir
        nested_media = tmp_path / "memory" / "users" / "user123" / "media" / "core"
        nested_media.mkdir(parents=True)
        nested_img = nested_media / "hidden3.webp"
        nested_img.write_bytes(b"")
        
        # Also create a dummy provenance ledger
        ledger = tmp_path / "memory" / "core" / "provenance_ledger.jsonl"
        ledger.write_text('{"type": "image", "filename": "test1.png", "metadata": {"prompt": "a test", "intention": "test intention"}, "timestamp": "2024-01-01"}\n')
        
        with patch("src.tools.document.os.getcwd", return_value=str(tmp_path)):
            # Test without search
            res = list_images()
            assert "Found 3 images" in res
            assert "test1.png" in res
            assert "auto_test2.jpg" in res
            assert "hidden3.webp" in res
            assert "a test" in res
            
            # Test with successful search
            res2 = list_images(search="test")
            assert "Found 2 images" in res2
            
            # Test with failing search
            res3 = list_images(search="missing")
            assert "No images matching 'missing'" in res3


class TestAutoSendFile:
    @pytest.mark.asyncio
    async def test_auto_send_missing_kwargs(self):
        from src.tools.document import _auto_send_file
        res = await _auto_send_file("path", "file.pdf", True, "url", {})
        assert res == ""

    @pytest.mark.asyncio
    async def test_auto_send_success(self):
        from src.tools.document import _auto_send_file
        
        class MockChannel:
            def __init__(self):
                self.called = False
            async def send(self, *args, **kwargs):
                self.called = True
                
        mock_channel = MockChannel()
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_discord_module = MagicMock()
        mock_discord_module.File.return_value = "file_obj"
        
        with patch.dict("sys.modules", {"discord": mock_discord_module}):
            res = await _auto_send_file(
                "path.pdf", "file.pdf", True, "url",
                {"bot": mock_bot, "channel_id": "123"}
            )
        assert res == " (Sent to channel)"
        assert mock_channel.called
        
        # Test fetch fallback
        mock_channel2 = MockChannel()
        mock_bot.get_channel.return_value = None
        mock_bot.fetch_channel = AsyncMock(return_value=mock_channel2)
        with patch.dict("sys.modules", {"discord": mock_discord_module}):
            res2 = await _auto_send_file(
                "path.pdf", "file.pdf", False, "",
                {"bot": mock_bot, "channel_id": "123"}
            )
        assert res2 == " (Sent to channel)"
        assert mock_channel2.called
        
    @pytest.mark.asyncio
    async def test_auto_send_error(self):
        from src.tools.document import _auto_send_file
        mock_bot = AsyncMock()
        
        with patch.dict("sys.modules", {"discord": None}):
            res = await _auto_send_file(
                "path.pdf", "file.pdf", True, "url",
                {"bot": mock_bot, "channel_id": "123"}
            )
        assert res == " (Send failed)"


class TestPreviewDocument:
    @pytest.mark.asyncio
    @patch("src.tools.document.Path")
    @patch("playwright.async_api.async_playwright")
    async def test_preview_fallback_playwright(self, mock_pw, mock_path):
        from src.tools.document import preview_document
        
        mock_p = MagicMock()
        mock_path.return_value = mock_p
        mock_p.exists.return_value = True
        mock_p.read_bytes.return_value = b"%PDF-1.4"
        mock_p.with_suffix.return_value = mock_p
        
        # Force fitz to fail so fallback is triggered
        mock_pw_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_pw.return_value.__aenter__.return_value = mock_pw_context
        mock_pw_context.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        with patch.dict("sys.modules", {"fitz": None}):
            res = await preview_document("test.pdf")
            
        assert "Preview image saved" in res
        mock_pw_context.chromium.launch.assert_called_once()
        mock_page.screenshot.assert_called_once()
        mock_page.set_content.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.tools.document.Path")
    async def test_preview_not_found(self, mock_path):
        from src.tools.document import preview_document
        mock_p = MagicMock()
        mock_path.return_value = mock_p
        mock_p.exists.return_value = False
        
        res = await preview_document("bad.pdf")
        assert "Error: PDF not found" in res
