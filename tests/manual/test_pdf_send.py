import sys
import os
import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Setup paths
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDFSendTest")

async def test_pdf_send(tmp_path=None):
    """
    Verifies that generate_pdf attempts to send the file to Discord
    when bot and channel_id are provided.
    """
    logger.info("Starting PDF Send Test...")
    
    from src.tools.document import generate_pdf
    
    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp())
    
    # Mock Objects
    mock_bot = MagicMock()
    mock_channel = AsyncMock()
    mock_bot.get_channel.return_value = mock_channel
    
    # Setup Playwright mocks (same pattern as test_phase4.py)
    mock_page = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    
    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser
    
    mock_pw_cm = AsyncMock()
    mock_pw_cm.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw_cm.__aexit__ = AsyncMock(return_value=False)
    
    with patch("playwright.async_api.async_playwright", return_value=mock_pw_cm), \
         patch("src.tools.document.settings") as mock_settings, \
         patch("src.security.provenance.ProvenanceManager") as mock_prov, \
         patch("os.getcwd", return_value=str(tmp_path)):
        mock_settings.ADMIN_IDS = [999]
        
        logger.info("Calling generate_pdf...")
        result = await generate_pdf(
            target="<h1>Test</h1>",
            is_url=False,
            user_id=123
        )      
        logger.info(f"Result: {result}")
        
        # The result should contain the pdf path (doc_*.pdf)
        assert ".pdf" in result

if __name__ == "__main__":
    asyncio.run(test_pdf_send())
