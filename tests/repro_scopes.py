
import sys
import os
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.privacy.scopes import ScopeManager, PrivacyScope
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_scope_hierarchy():
    print("--- Testing Scope Hierarchy ---")
    
    # Ensure privacy scopes enabled
    settings.ENABLE_PRIVACY_SCOPES = True
    
    # Core Private (God Mode)
    assert ScopeManager.check_access(PrivacyScope.CORE_PRIVATE, PrivacyScope.PRIVATE) == True, "CORE_PRIVATE should see PRIVATE"
    assert ScopeManager.check_access(PrivacyScope.CORE_PRIVATE, PrivacyScope.CORE_PUBLIC) == True, "CORE_PRIVATE should see CORE_PUBLIC"
    print("✅ CORE_PRIVATE Access Verified")
    
    # Core Public
    # Can see PUBLIC + CORE_PUBLIC
    # Cannot see PRIVATE
    assert ScopeManager.check_access(PrivacyScope.CORE_PUBLIC, PrivacyScope.PUBLIC) == True, "CORE_PUBLIC should see PUBLIC"
    assert ScopeManager.check_access(PrivacyScope.CORE_PUBLIC, PrivacyScope.CORE_PUBLIC) == True, "CORE_PUBLIC should see CORE_PUBLIC"
    assert ScopeManager.check_access(PrivacyScope.CORE_PUBLIC, PrivacyScope.PRIVATE) == False, "CORE_PUBLIC should NOT see PRIVATE"
    print("✅ CORE_PUBLIC Access Verified")
    
    # Public
    # Can see PUBLIC + CORE_PUBLIC
    # Cannot see PRIVATE
    assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.PUBLIC) == True, "PUBLIC should see PUBLIC"
    assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.CORE_PUBLIC) == True, "PUBLIC should see CORE_PUBLIC"
    assert ScopeManager.check_access(PrivacyScope.PUBLIC, PrivacyScope.PRIVATE) == False, "PUBLIC should NOT see PRIVATE"
    print("✅ PUBLIC Access Verified")
    
    # Private (User)
    # Can see PRIVATE (Self) + PUBLIC + CORE_PUBLIC
    # Can see CORE_PRIVATE? No.
    assert ScopeManager.check_access(PrivacyScope.PRIVATE, PrivacyScope.PRIVATE) == True, "PRIVATE should see PRIVATE"
    assert ScopeManager.check_access(PrivacyScope.PRIVATE, PrivacyScope.PUBLIC) == True, "PRIVATE should see PUBLIC"
    assert ScopeManager.check_access(PrivacyScope.PRIVATE, PrivacyScope.CORE_PUBLIC) == True, "PRIVATE should see CORE_PUBLIC"
    assert ScopeManager.check_access(PrivacyScope.PRIVATE, PrivacyScope.CORE_PRIVATE) == False, "PRIVATE should NOT see CORE_PRIVATE"
    print("✅ PRIVATE Access Verified")

if __name__ == "__main__":
    test_scope_hierarchy()
