"""
Mock Integrity Audit
Scans all test files for:
1. Async functions mocked with MagicMock instead of AsyncMock
2. Tests that mock so heavily they test nothing real
3. Tests that never actually assert anything meaningful
"""
import ast
import os
import re
import sys
from pathlib import Path
from collections import defaultdict


def scan_test_files(root_dir):
    tests_dir = Path(root_dir) / "tests"
    src_dir = Path(root_dir) / "src"
    
    # Phase 1: Collect all async function names from src/
    async_funcs = set()
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    async_funcs.add(node.name)
        except:
            continue
    
    print(f"Found {len(async_funcs)} unique async function names in src/\n")
    
    # Phase 2: Scan test files for mock usage
    total_test_files = 0
    total_test_functions = 0
    total_mock_patches = 0
    mock_issues = []
    empty_tests = []
    over_mocked_tests = []
    
    for py_file in tests_dir.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
            continue
        
        total_test_files += 1
        try:
            source = py_file.read_text(encoding="utf-8")
            lines = source.split("\n")
        except:
            continue
        
        rel_path = py_file.relative_to(root_dir)
        
        # Count test functions
        test_func_count = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def test_") or stripped.startswith("async def test_"):
                test_func_count += 1
        total_test_functions += test_func_count
        
        # Count @patch and patch() calls
        patch_count = source.count("@patch(") + source.count("@patch.object(")
        patch_count += source.count("patch(") + source.count("patch.object(")
        # Rough dedup (each @patch also shows up in patch() count)
        inline_patches = source.count("with patch(") + source.count("with patch.object(")
        decorator_patches = source.count("@patch(") + source.count("@patch.object(")
        total_patches = inline_patches + decorator_patches
        total_mock_patches += total_patches
        
        # Check for async functions being mocked with MagicMock
        for i, line in enumerate(lines):
            # Look for patterns like: mock_observe = MagicMock() where observe is async
            # Or: patch('...observe', MagicMock())
            # Or: patch('...observe') without new=AsyncMock
            
            for func_name in async_funcs:
                # Check if this line patches/mocks an async function
                if func_name in line:
                    lineno = i + 1
                    stripped = line.strip()
                    
                    # Pattern 1: @patch('path.to.async_func') without AsyncMock
                    if f"@patch(" in stripped and func_name in stripped:
                        if "AsyncMock" not in stripped and "new_callable=AsyncMock" not in stripped:
                            # Check if the next few lines set it up as AsyncMock
                            context = "\n".join(lines[max(0,i-1):min(len(lines),i+5)])
                            if "AsyncMock" not in context:
                                mock_issues.append((str(rel_path), lineno, func_name, stripped, "DECORATOR_PATCH"))
                    
                    # Pattern 2: MagicMock() assigned to something with async func name
                    if f"MagicMock()" in stripped and func_name in stripped.lower():
                        mock_issues.append((str(rel_path), lineno, func_name, stripped, "MAGICMOCK_ASSIGN"))
                    
                    # Pattern 3: patch('...async_func', MagicMock())
                    if "patch(" in stripped and "MagicMock()" in stripped and func_name in stripped:
                        mock_issues.append((str(rel_path), lineno, func_name, stripped, "PATCH_WITH_MAGICMOCK"))
        
        # Check for tests with no assertions
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        # Check if the function body has any assert statements
                        has_assert = False
                        has_mock_assert = False
                        has_pytest_raises = False
                        for child in ast.walk(node):
                            if isinstance(child, ast.Assert):
                                has_assert = True
                            if isinstance(child, ast.Attribute):
                                if hasattr(child, 'attr') and child.attr in (
                                    'assert_called', 'assert_called_once', 
                                    'assert_called_with', 'assert_called_once_with',
                                    'assert_any_call', 'assert_not_called',
                                    'assert_awaited', 'assert_awaited_once',
                                    'assert_awaited_with', 'assert_awaited_once_with',
                                    'assert_any_await', 'assert_not_awaited',
                                    'assertEqual', 'assertTrue', 'assertFalse',
                                    'assertRaises', 'assertIn', 'assertIsNotNone',
                                    'assertIsNone', 'assertGreater', 'assertLess',
                                    'assertNotEqual', 'assertLessEqual',
                                    'assertGreaterEqual', 'assertNotIn',
                                    'assertNotIsNone', 'assertAlmostEqual',
                                    'assertRegex', 'assertWarns', 'fail',
                                ):
                                    has_mock_assert = True
                                # Detect pytest.raises / pytest.fail / pytest.warns
                                if hasattr(child, 'attr') and child.attr in ('raises', 'fail', 'warns'):
                                    if isinstance(child.value, ast.Name) and child.value.id == 'pytest':
                                        has_pytest_raises = True
                        
                        if not has_assert and not has_mock_assert and not has_pytest_raises:
                            empty_tests.append((str(rel_path), node.lineno, node.name))
        except:
            pass
        
        # Flag heavily mocked files
        if test_func_count > 0 and total_patches > 0:
            ratio = total_patches / test_func_count
            if ratio > 5:  # More than 5 patches per test function
                over_mocked_tests.append((str(rel_path), test_func_count, total_patches, ratio))
    
    # Report
    print("=" * 80)
    print("TEST SUITE MOCK INTEGRITY AUDIT")
    print("=" * 80)
    print(f"\nTest files scanned: {total_test_files}")
    print(f"Total test functions: {total_test_functions}")
    print(f"Total mock patches: {total_mock_patches}")
    
    print(f"\n{'=' * 80}")
    print(f"🚨 ASYNC FUNCTIONS MOCKED WITH MagicMock (should be AsyncMock)")
    print(f"{'=' * 80}")
    if mock_issues:
        for fpath, lineno, func_name, line, pattern in mock_issues:
            print(f"  {fpath}:{lineno} — {func_name}() [{pattern}]")
            print(f"    {line}")
    else:
        print("  None found ✅")
    
    print(f"\n{'=' * 80}")
    print(f"⚠️  TEST FUNCTIONS WITH NO ASSERTIONS ({len(empty_tests)} found)")
    print(f"{'=' * 80}")
    for fpath, lineno, name in empty_tests[:30]:
        print(f"  {fpath}:{lineno} — {name}()")
    if len(empty_tests) > 30:
        print(f"  ... and {len(empty_tests) - 30} more")
    
    print(f"\n{'=' * 80}")
    print(f"📊 HEAVILY MOCKED TEST FILES (>5 patches per test)")
    print(f"{'=' * 80}")
    if over_mocked_tests:
        for fpath, funcs, patches, ratio in sorted(over_mocked_tests, key=lambda x: -x[3]):
            print(f"  {fpath}: {funcs} tests, {patches} patches ({ratio:.1f}x ratio)")
    else:
        print("  None found ✅")
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Async mock issues: {len(mock_issues)}")
    print(f"  Tests without assertions: {len(empty_tests)}")
    print(f"  Heavily mocked files: {len(over_mocked_tests)}")
    
    total_real_issues = len(mock_issues) + len(empty_tests)
    if total_real_issues > 0:
        print(f"\n  ⚠️  {total_real_issues} issues found that may reduce test effectiveness")
    else:
        print(f"\n  ✅ Test suite looks healthy")
    
    return mock_issues, empty_tests, over_mocked_tests


if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    issues, empty, over = scan_test_files(root)
