"""
Tests for Surgical File Editing
Tests the surgical_edit utility and updated file tools.
"""
import pytest
import os
import tempfile
from src.tools.file_utils import surgical_edit, VALID_MODES


class TestSurgicalEdit:
    """Tests for surgical_edit function."""
    
    @pytest.fixture
    def temp_file(self):
        """Create a temp file for testing."""
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)
    
    def test_append_mode(self, temp_file):
        """Test append adds to end."""
        with open(temp_file, "w") as f:
            f.write("Line 1")
        
        success, msg = surgical_edit(temp_file, "append", "Line 2")
        
        assert success
        with open(temp_file) as f:
            content = f.read()
        assert "Line 1" in content
        assert "Line 2" in content
    
    def test_overwrite_mode(self, temp_file):
        """Test overwrite replaces all."""
        with open(temp_file, "w") as f:
            f.write("Old content")
        
        success, msg = surgical_edit(temp_file, "overwrite", "New content")
        
        assert success
        with open(temp_file) as f:
            content = f.read()
        assert content == "New content"
        assert "Old" not in content
    
    def test_replace_mode(self, temp_file):
        """Test replace swaps first occurrence."""
        with open(temp_file, "w") as f:
            f.write("Hello world, hello universe")
        
        success, msg = surgical_edit(temp_file, "replace", "REPLACED", "world")
        
        assert success
        with open(temp_file) as f:
            content = f.read()
        assert "REPLACED" in content
        assert "hello universe" in content  # Second occurrence untouched
    
    def test_replace_all_mode(self, temp_file):
        """Test replace_all swaps all occurrences."""
        with open(temp_file, "w") as f:
            f.write("cat cat cat")
        
        success, msg = surgical_edit(temp_file, "replace_all", "dog", "cat")
        
        assert success
        with open(temp_file) as f:
            content = f.read()
        assert content == "dog dog dog"
    
    def test_delete_mode(self, temp_file):
        """Test delete removes matching lines."""
        with open(temp_file, "w") as f:
            f.write("Keep this\nDelete this SECRET\nKeep that")
        
        success, msg = surgical_edit(temp_file, "delete", "", "SECRET")
        
        assert success
        with open(temp_file) as f:
            content = f.read()
        assert "Keep this" in content
        assert "Keep that" in content
        assert "SECRET" not in content
    
    def test_insert_after_mode(self, temp_file):
        """Test insert_after adds line after target."""
        with open(temp_file, "w") as f:
            f.write("Line A\nLine B\nLine C")
        
        success, msg = surgical_edit(temp_file, "insert_after", "INSERTED", "Line B")
        
        assert success
        with open(temp_file) as f:
            lines = f.read().split("\n")
        assert lines.index("INSERTED") == lines.index("Line B") + 1
    
    def test_insert_before_mode(self, temp_file):
        """Test insert_before adds line before target."""
        with open(temp_file, "w") as f:
            f.write("Line A\nLine B\nLine C")
        
        success, msg = surgical_edit(temp_file, "insert_before", "INSERTED", "Line B")
        
        assert success
        with open(temp_file) as f:
            lines = f.read().split("\n")
        assert lines.index("INSERTED") == lines.index("Line B") - 1
    
    def test_regex_replace_mode(self, temp_file):
        """Test regex_replace with pattern."""
        with open(temp_file, "w") as f:
            f.write("User ID: 12345, User ID: 67890")
        
        success, msg = surgical_edit(temp_file, "regex_replace", "REDACTED", r"User ID: \d+")
        
        assert success
        with open(temp_file) as f:
            content = f.read()
        assert "REDACTED" in content
        assert "12345" not in content
    
    def test_replace_target_not_found(self, temp_file):
        """Test replace fails gracefully when target missing."""
        with open(temp_file, "w") as f:
            f.write("No match here")
        
        success, msg = surgical_edit(temp_file, "replace", "new", "NOTFOUND")
        
        assert not success
        assert "not found" in msg.lower()
    
    def test_invalid_mode_rejected(self, temp_file):
        """Test invalid mode is rejected."""
        success, msg = surgical_edit(temp_file, "invalid_mode", "content")
        
        assert not success
        assert "Unknown mode" in msg
    
    def test_valid_modes_constant(self):
        """Verify all 8 modes are exported."""
        assert len(VALID_MODES) == 8
        assert "append" in VALID_MODES
        assert "overwrite" in VALID_MODES
        assert "replace" in VALID_MODES
        assert "replace_all" in VALID_MODES
        assert "delete" in VALID_MODES
        assert "insert_after" in VALID_MODES
        assert "insert_before" in VALID_MODES
        assert "regex_replace" in VALID_MODES


class TestUpdatePersonaSurgical:
    """Tests for update_persona surgical modes."""
    
    def test_update_persona_has_target_param(self):
        """Verify update_persona accepts target parameter."""
        from src.tools.memory import update_persona
        import inspect
        sig = inspect.signature(update_persona)
        assert "target" in sig.parameters
        assert "mode" in sig.parameters


class TestCreateProgramSurgical:
    """Tests for create_program surgical modes."""
    
    def test_create_program_has_target_param(self):
        """Verify create_program accepts target parameter."""
        from src.tools.coding import create_program
        import inspect
        sig = inspect.signature(create_program)
        assert "target" in sig.parameters
        assert "mode" in sig.parameters
