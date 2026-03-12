"""
Regression tests for Ontologist mediator routing crash and document preview.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestOntologistContradictionHandling:
    """Tests that _route_to_mediator handles non-dict contradiction values."""

    def _make_ontologist(self):
        from src.lobes.memory.ontologist import OntologistAbility
        # Create a mock that has cerebrum=None (triggers early-return in _route_to_mediator)
        ont = MagicMock(spec=OntologistAbility)
        ont.cerebrum = None
        # Bind the real method
        ont._route_to_mediator = OntologistAbility._route_to_mediator.__get__(ont)
        return ont

    @pytest.mark.asyncio
    async def test_contradiction_as_dict(self):
        """Dict contradiction should extract 'object' field normally."""
        ont = self._make_ontologist()
        result = await ont._route_to_mediator(
            "Earth", "SHAPE", "flat",
            contradiction={"subject": "Earth", "predicate": "SHAPE", "object": "spheroid"},
            user_id="123", source_url=None
        )
        assert "spheroid" in result
        assert "Conflict detected" in result

    @pytest.mark.asyncio
    async def test_contradiction_as_string(self):
        """String contradiction should not crash with .get() AttributeError."""
        ont = self._make_ontologist()
        result = await ont._route_to_mediator(
            "Earth", "SHAPE", "flat",
            contradiction="Conflicting fact found in CORE",
            user_id="123", source_url=None
        )
        # Should NOT crash, and should include the string as context
        assert "Conflict detected" in result
        assert "Conflicting fact" in result

    @pytest.mark.asyncio
    async def test_contradiction_as_bool(self):
        """Boolean True contradiction should not crash."""
        ont = self._make_ontologist()
        result = await ont._route_to_mediator(
            "Earth", "SHAPE", "flat",
            contradiction=True,
            user_id="123", source_url=None
        )
        assert "Conflict detected" in result

    @pytest.mark.asyncio
    async def test_contradiction_as_none(self):
        """None contradiction should not crash."""
        ont = self._make_ontologist()
        result = await ont._route_to_mediator(
            "Earth", "SHAPE", "flat",
            contradiction=None,
            user_id="123", source_url=None
        )
        # Should handle gracefully
        assert result is not None


class TestPreviewDocumentNoCrash:
    """Tests that preview_document doesn't crash on file:// PDFs."""

    @pytest.mark.asyncio
    async def test_preview_missing_pdf(self):
        """Should return error message for non-existent PDF."""
        from src.tools.document import preview_document
        result = await preview_document("/tmp/nonexistent_file_abc123.pdf")
        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_preview_uses_fitz_when_available(self, tmp_path):
        """When PyMuPDF is available, preview should use it (no Playwright needed)."""
        import fitz

        pdf_path = tmp_path / "test.pdf"
        preview_path = tmp_path / "test.preview.png"

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Test PDF content")
        doc.save(str(pdf_path))
        doc.close()

        from src.tools.document import preview_document
        result = await preview_document(str(pdf_path))

        assert "Preview image saved" in result
        assert preview_path.exists()

    @pytest.mark.asyncio
    async def test_preview_does_not_use_file_goto(self):
        """Verify the old page.goto(file://) pattern is no longer used."""
        import inspect
        from src.tools.document import preview_document
        source = inspect.getsource(preview_document)
        # The old crashing pattern should be gone
        assert 'page.goto(f"file://' not in source
        assert "page.goto" not in source or "set_content" in source
