import os
import pytest
from src.prompts.manager import PromptManager

def test_prompt_manager_core_files_exist():
    """
    REGRESSION TEST: Ensure that the essential prompt files required by PromptManager
    (dynamic_context.txt, identity_core.txt, kernel_backup.txt) are present on disk
    and load successfully without triggering SecureLoader file not found warnings.
    """
    manager = PromptManager()
    
    # Verify the paths are resolved correctly
    assert manager.kernel_file.endswith("kernel_backup.txt")
    assert manager.architecture_file.endswith("dynamic_context.txt")
    assert manager.identity_core_file.endswith("identity_core.txt")
    
    # Read files to ensure SecureLoader successfully loads them 
    # (SecureLoader handles both .enc and .txt files)
    kernel_content = manager._read_file(manager.kernel_file)
    architecture_content = manager._read_file(manager.architecture_file)
    identity_content = manager._read_file(manager.identity_core_file)
    
    # If the files are missing, SecureLoader logs a warning and returns ""
    assert kernel_content != "", f"kernel_backup.txt is missing from {manager.prompt_dir}"
    assert architecture_content != "", f"dynamic_context.txt is missing from {manager.prompt_dir}"
    assert identity_content != "", f"identity_core.txt is missing from {manager.prompt_dir}"

def test_prompt_manager_builds_prompt():
    """
    REGRESSION TEST: Verify that get_system_prompt can render a full prompt string
    without raising KeyError on missing template variables.
    """
    manager = PromptManager()
    prompt = manager.get_system_prompt(
        timestamp="2026-01-01T00:00:00",
        scope="PUBLIC",
        user_id="12345",
        user_name="TestUser",
        active_engine="TestEngine",
        active_mode="Standard",
        is_core=False
    )
    
    assert prompt != ""
    assert "TestEngine" in prompt
    assert "TestUser" in prompt
    # Ensure our newly reconstructed core logic is present
    assert "autonomy" in prompt.lower()
