import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import time

@pytest.fixture
def mock_playwright():
    """Mock the playwright dependency for generate_pdf tests."""
    with patch("playwright.async_api.async_playwright") as mock_pw:
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        yield mock_page

@pytest.mark.asyncio
async def test_generate_pdf_hallucination_override_long_text(mock_playwright):
    """
    Test that if the LLM passes a long markdown string but maliciously/accidentally
    sets is_url=True, the system overrides it and treats it as markdown content.
    """
    from src.tools.document import generate_pdf

    long_markdown_content = "# Test Document\n\n" * 50
    
    with patch('src.tools.document.Path') as mock_path, \
         patch('src.security.provenance.ProvenanceManager.log_artifact') as mock_log:
             
        # Execute the function with the hallucinated flag
        result = await generate_pdf(
            target=long_markdown_content,
            is_url=True,  # The hallucinated flag
            user_id=123,
            request_scope="PUBLIC"
        )
        
        # Verify it successfully ran
        assert "SUCCESS" in result
        
        # Verify that page.set_content was called (meaning it treated it as HTML/MD)
        # And NOT page.goto (which is for URLs)
        assert mock_playwright.set_content.called, "Should have used set_content for text"
        assert not mock_playwright.goto.called, "Should NOT have used goto for text"

@pytest.mark.asyncio
async def test_generate_pdf_hallucination_override_not_http(mock_playwright):
    """
    Test that if the LLM passes a string that does not start with http
    and sets is_url=True, the system overrides it.
    """
    from src.tools.document import generate_pdf

    not_a_url_content = "This is just some random text without http."
    
    with patch('src.tools.document.Path'), \
         patch('src.security.provenance.ProvenanceManager.log_artifact'):
             
        # Execute the function with the hallucinated flag
        result = await generate_pdf(
            target=not_a_url_content,
            is_url=True,  # The hallucinated flag
            user_id=123,
            request_scope="PUBLIC"
        )
        
        assert "SUCCESS" in result
        assert mock_playwright.set_content.called
        assert not mock_playwright.goto.called

@pytest.mark.asyncio
async def test_generate_pdf_valid_url(mock_playwright):
    """
    Test that a valid URL is still processed as a URL.
    """
    from src.tools.document import generate_pdf

    valid_url = "https://example.com/research-paper"
    
    with patch('src.tools.document.Path'), \
         patch('src.security.provenance.ProvenanceManager.log_artifact'):
             
        result = await generate_pdf(
            target=valid_url,
            is_url=True,
            user_id=123,
            request_scope="PUBLIC"
        )
        
        assert "SUCCESS" in result
        assert mock_playwright.goto.called, "Should have used goto for a valid URL"
        assert not mock_playwright.set_content.called, "Should NOT have used set_content for a URL"
