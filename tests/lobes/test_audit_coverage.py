"""
Tests for AuditAbility (Superego)
Targeting 95%+ coverage for src/lobes/superego/audit.py
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.lobes.superego.audit import AuditAbility


class TestAuditAbility:
    """Tests for AuditAbility class."""
    
    def setup_method(self):
        """Setup mock bot."""
        self.mock_bot = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_bot.engine_manager.get_active_engine.return_value = self.mock_engine
        
        async def mock_run_in_executor(executor, func, *args):
            return func(*args) if args else func()
        self.mock_bot.loop.run_in_executor = mock_run_in_executor
        
        self.ability = AuditAbility(self.mock_bot)
    
    @pytest.mark.asyncio
    async def test_audit_empty_response(self):
        """Test audit with empty response passes."""
        result = await self.ability.audit_response("hi", "", [])
        
        assert result["allowed"] is True
    
    @pytest.mark.asyncio
    async def test_audit_response_passes(self):
        """Test audit passes valid response."""
        self.mock_engine.generate_response.return_value = "PASS: Response is valid"
        
        result = await self.ability.audit_response(
            user_msg="What's 2+2?",
            bot_msg="2+2 equals 4",
            tool_outputs=[]
        )
        
        assert result["allowed"] is True
    
    @pytest.mark.asyncio
    async def test_audit_with_tool_outputs(self):
        """Test audit with tool execution context."""
        self.mock_engine.generate_response.return_value = "PASS"
        
        result = await self.ability.audit_response(
            user_msg="Read the config",
            bot_msg="Here's the config content",
            tool_outputs=[{"tool": "read_file", "output": "config data"}]
        )
        
        assert result["allowed"] is True
    
    @pytest.mark.asyncio
    async def test_audit_with_session_history(self):
        """Test audit with session history context."""
        self.mock_engine.generate_response.return_value = "PASS"
        
        result = await self.ability.audit_response(
            user_msg="Continue",
            bot_msg="Continuing from before",
            tool_outputs=[{"tool": "read_file", "output": "data"}],
            session_history=[
                {"tool": "search_codebase", "output": "found", "timestamp": "earlier"},
                {"tool": "read_file", "output": "content", "timestamp": "now"}
            ]
        )
        
        assert result["allowed"] is True
    
    @pytest.mark.asyncio
    async def test_audit_with_images(self):
        """Test audit with images context."""
        self.mock_engine.generate_response.return_value = "PASS"
        
        result = await self.ability.audit_response(
            user_msg="What's in this image?",
            bot_msg="I see a cat",
            tool_outputs=[],
            images=["image1.png"]
        )
        
        assert result["allowed"] is True
    
    @pytest.mark.asyncio
    async def test_audit_error_fails_open(self):
        """Test audit fails open on error."""
        self.mock_engine.generate_response.side_effect = Exception("API Error")
        
        result = await self.ability.audit_response(
            user_msg="test",
            bot_msg="response",
            tool_outputs=[]
        )
        
        # Should fail open (allow) on error
        assert result["allowed"] is True
        assert "Audit Error" in result["reason"]


class TestVerifyResponseIntegrity:
    """Tests for verify_response_integrity method."""
    
    def setup_method(self):
        """Setup."""
        self.mock_bot = MagicMock()
        self.ability = AuditAbility(self.mock_bot)
    
    def test_no_claims_passes(self):
        """Test response with no verification claims passes."""
        valid, reason = self.ability.verify_response_integrity(
            "Hello! How can I help you today?",
            []
        )
        
        assert valid is True
        assert "Verified" in reason
    
    def test_claim_with_matching_tool(self):
        """Test claim with matching tool execution passes."""
        valid, reason = self.ability.verify_response_integrity(
            "I checked the code and found the issue",
            [{"tool": "search_codebase", "output": "found"}]
        )
        
        assert valid is True
    
    def test_claim_without_tool_passes_disabled(self):
        """Test claim without tool execution now passes (heuristics disabled)."""
        valid, reason = self.ability.verify_response_integrity(
            "I checked the code and found the issue",
            []  # No tools executed — but heuristics are disabled
        )
        
        assert valid is True
        assert "Verified" in reason
    
    def test_multiple_claims_passes_disabled(self):
        """Test multiple claims now pass (heuristics disabled)."""
        valid, reason = self.ability.verify_response_integrity(
            "I checked the code and verified in the database",
            []  # No tools for either claim — but heuristics disabled
        )
        
        assert valid is True
        assert "Verified" in reason
    
    def test_scanned_files_with_list_dir(self):
        """Test 'scanned files' claim with list_dir."""
        valid, reason = self.ability.verify_response_integrity(
            "I scanned the files in that directory",
            [{"tool": "list_dir", "output": "file1, file2"}]
        )
        
        assert valid is True
    
    def test_checked_memory_with_recall(self):
        """Test 'checked your memory' claim with recall."""
        valid, reason = self.ability.verify_response_integrity(
            "I checked your memory and found the answer",
            [{"tool": "recall", "output": "memory content"}]
        )
        
        assert valid is True
    
    def test_checked_reality(self):
        """Test 'checked reality' claim."""
        valid, reason = self.ability.verify_response_integrity(
            "I checked reality using web search",
            [{"tool": "search_web", "output": "results"}]
        )
        
        assert valid is True
    
    def test_tool_history_as_strings(self):
        """Test tool history as string format."""
        valid, reason = self.ability.verify_response_integrity(
            "I scanned the files",
            ["list_dir: output"]  # String format
        )
        
        assert valid is True
    
    def test_case_insensitive(self):
        """Test claims are case-insensitive."""
        valid, reason = self.ability.verify_response_integrity(
            "I CHECKED THE CODE",
            [{"tool": "read_file", "output": "content"}]
        )
        
        assert valid is True
