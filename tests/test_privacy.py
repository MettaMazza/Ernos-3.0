import pytest
from unittest.mock import MagicMock
from src.privacy.scopes import PrivacyScope, ScopeManager

def test_privacy_enum():
    assert PrivacyScope.CORE.value == 1
    assert PrivacyScope.OPEN.value == 4

def test_scope_manager_paths():
    # Test directory resolution
    # We will trust integration tests for mkdir or use checking
    path = ScopeManager.get_user_home(123)
    assert "users/123" in str(path)
    
    path_core = ScopeManager.get_user_home(None)
    assert "memory/core" in str(path_core)

def test_scope_manager_disabled(mocker):
    # settings.ENABLE_PRIVACY_SCOPES is True in settings.py now, so we must mock False
    mocker.patch("config.settings.ENABLE_PRIVACY_SCOPES", False)
    assert ScopeManager.get_scope(123, 456) == PrivacyScope.OPEN
    assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.CORE) is True

def test_scope_manager_enabled(mocker):
    mocker.patch("config.settings.ENABLE_PRIVACY_SCOPES", True)
    
    # Scope is determined by channel TYPE, not user identity
    # All guild channel conversations are PUBLIC
    assert ScopeManager.get_scope(1, 999) == PrivacyScope.PUBLIC
    assert ScopeManager.get_scope(2, 100) == PrivacyScope.PUBLIC
    
    # Access checks
    assert ScopeManager.check_access(PrivacyScope.CORE, PrivacyScope.PRIVATE) is True
    assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.PUBLIC) is True
    assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.CORE) is False
