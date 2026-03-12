"""
Coverage tests for src/engines/cognition_retry.py.
Targets 50 uncovered lines across: extract_files, strip_output_artifacts,
_static_fallback, _generate_exhaustion_response, forced_retry_loop branches.
"""
import pytest
import re
from unittest.mock import patch, MagicMock, AsyncMock


# ── extract_files ────────────────────────────────────────
class TestExtractFiles:
    def test_empty_history(self):
        from src.engines.cognition_retry import extract_files
        assert extract_files("") == []

    def test_generated_image(self):
        from src.engines.cognition_retry import extract_files
        history = "Created image at /tmp/output/generated_portrait.png successfully"
        result = extract_files(history)
        assert "/tmp/output/generated_portrait.png" in result

    def test_screenshot(self):
        from src.engines.cognition_retry import extract_files
        history = "SCREENSHOT_FILE:/tmp/screenshots/generated_screen.png"
        result = extract_files(history)
        assert "/tmp/screenshots/generated_screen.png" in result

    def test_pdf_suppresses_images(self):
        from src.engines.cognition_retry import extract_files
        history = (
            "Created /tmp/generated_portrait.png\n"
            "PDF rendered: /tmp/report.pdf\n"
        )
        result = extract_files(history)
        assert "/tmp/report.pdf" in result
        # Image should be suppressed when PDF present
        assert "/tmp/generated_portrait.png" not in result

    def test_pdf_allows_non_images(self):
        from src.engines.cognition_retry import extract_files
        history = (
            "Audio at /tmp/output/generated_song.mp3\n"
            "PDF rendered: /tmp/report.pdf\n"
        )
        result = extract_files(history)
        assert "/tmp/report.pdf" in result
        assert "/tmp/output/generated_song.mp3" in result

    def test_embedded_images_excluded(self):
        from src.engines.cognition_retry import extract_files
        history = (
            'embed_image(image_path="/tmp/generated_chart.png")\n'
            "Created /tmp/generated_chart.png\n"
        )
        result = extract_files(history)
        assert "/tmp/generated_chart.png" not in result

    def test_listed_images_excluded(self):
        from src.engines.cognition_retry import extract_files
        history = (
            "   Path: /tmp/generated_old.png\n"
            "Created /tmp/generated_old.png\n"
        )
        result = extract_files(history)
        assert "/tmp/generated_old.png" not in result

    def test_no_duplicates(self):
        from src.engines.cognition_retry import extract_files
        history = (
            "Created /tmp/generated_img.png\n"
            "Done: /tmp/generated_img.png\n"
        )
        result = extract_files(history)
        assert result.count("/tmp/generated_img.png") == 1

    def test_kg_visualizer(self):
        from src.engines.cognition_retry import extract_files
        history = "Generated /tmp/vis/kg_visualizer_graph.png"
        result = extract_files(history)
        assert "/tmp/vis/kg_visualizer_graph.png" in result


# ── strip_output_artifacts ───────────────────────────────
class TestStripOutputArtifacts:
    def test_strips_image_tags(self):
        from src.engines.cognition_retry import strip_output_artifacts
        text = "Here is the result [IMAGE: some_image.png] done"
        result = strip_output_artifacts(text, ["/tmp/img.png"])
        assert "[IMAGE:" not in result

    def test_strips_screenshot_sentinels(self):
        from src.engines.cognition_retry import strip_output_artifacts
        text = "Result: 📸 SCREENSHOT_FILE:/tmp/screen.png done"
        result = strip_output_artifacts(text, ["/tmp/screen.png"])
        assert "SCREENSHOT_FILE" not in result

    def test_strips_src_tags(self):
        from src.engines.cognition_retry import strip_output_artifacts
        text = "Hello [SRC:KG:fact123] world [SRC:VR:mem456]"
        result = strip_output_artifacts(text, [])
        assert "[SRC:" not in result
        assert "Hello" in result

    def test_no_files_no_strip(self):
        from src.engines.cognition_retry import strip_output_artifacts
        text = "Normal response text"
        result = strip_output_artifacts(text, [])
        assert result == "Normal response text"

    def test_empty_text(self):
        from src.engines.cognition_retry import strip_output_artifacts
        result = strip_output_artifacts("", ["/tmp/file.png"])
        assert result == ""

    def test_collapses_multiple_newlines(self):
        from src.engines.cognition_retry import strip_output_artifacts
        text = "Line 1\n\n\n\n\nLine 2"
        result = strip_output_artifacts(text, ["/tmp/file.png"])
        assert "\n\n\n" not in result


# ── _static_fallback ────────────────────────────────────
class TestStaticFallback:
    def test_returns_string(self):
        from src.engines.cognition_retry import _static_fallback
        result = _static_fallback()
        assert "rephrasing" in result
        assert isinstance(result, str)


# ── _generate_exhaustion_response ────────────────────────
class TestGenerateExhaustionResponse:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.engines.cognition_retry import _generate_exhaustion_response
        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_bot.loop.run_in_executor = AsyncMock(return_value="I struggled with this question.")
        tool_pattern = re.compile(r"\[TOOL_CALL\]")

        result = await _generate_exhaustion_response(
            mock_bot, mock_engine, "What is 2+2?", "hallucination", 5, tool_pattern
        )
        assert "struggled" in result

    @pytest.mark.asyncio
    async def test_tool_call_in_response(self):
        from src.engines.cognition_retry import _generate_exhaustion_response
        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_bot.loop.run_in_executor = AsyncMock(return_value="[TOOL_CALL] bad")
        tool_pattern = re.compile(r"\[TOOL_CALL\]")

        result = await _generate_exhaustion_response(
            mock_bot, mock_engine, "test", "reason", 3, tool_pattern
        )
        assert "rephrasing" in result  # Falls back to static

    @pytest.mark.asyncio
    async def test_exception_fallback(self):
        from src.engines.cognition_retry import _generate_exhaustion_response
        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_bot.loop.run_in_executor = AsyncMock(side_effect=RuntimeError("fail"))
        tool_pattern = re.compile(r"\[TOOL_CALL\]")

        result = await _generate_exhaustion_response(
            mock_bot, mock_engine, "test", "reason", 3, tool_pattern
        )
        assert "rephrasing" in result
