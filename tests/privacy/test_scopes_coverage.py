import pytest
from unittest.mock import MagicMock, patch
from src.privacy.scopes import ScopeManager, PrivacyScope
from config import settings

def test_get_user_home_none():
    path = ScopeManager.get_user_home(None)
    assert path.name == "core"

def test_get_scope_disabled():
    with patch("config.settings.ENABLE_PRIVACY_SCOPES", False):
        assert ScopeManager.get_scope(1, 1) == PrivacyScope.OPEN

def test_check_access_disabled():
    with patch("config.settings.ENABLE_PRIVACY_SCOPES", False):
        assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.CORE) is True

def test_check_access_private_vs_core():
    # Private cannot see Core
    with patch("config.settings.ENABLE_PRIVACY_SCOPES", True):
        assert ScopeManager.check_access(PrivacyScope.PRIVATE, PrivacyScope.CORE) is False

def test_check_access_public_vs_private():
    # Public cannot see Private
    with patch("config.settings.ENABLE_PRIVACY_SCOPES", True):
        assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.PRIVATE) is False

def test_check_access_unknown():
    # Unknown (e.g. Open) trying to access something?
    # Logic returns False at end
    with patch("config.settings.ENABLE_PRIVACY_SCOPES", True):
        assert ScopeManager.check_access(PrivacyScope.OPEN, PrivacyScope.PUBLIC) is False
