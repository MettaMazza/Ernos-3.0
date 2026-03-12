"""
Full Async Audit Script
Scans every .py file in src/ for async def functions,
then finds every call site and checks if 'await' is used.
Reports any missing awaits.
"""
import ast
import os
import sys
from pathlib import Path
from collections import defaultdict

class AsyncDefCollector(ast.NodeVisitor):
    """Collect all async function/method names from a file."""
    def __init__(self, filepath):
        self.filepath = filepath
        self.async_funcs = []  # list of (name, lineno, class_name)
    
    def visit_AsyncFunctionDef(self, node):
        # Check if inside a class
        class_name = None
        for parent in ast.walk(ast.parse(open(self.filepath).read())):
            if isinstance(parent, ast.ClassDef):
                for child in ast.walk(parent):
                    if child is node:
                        class_name = parent.name
                        break
        self.async_funcs.append((node.name, node.lineno, class_name))
        self.generic_visit(node)


class MissingAwaitDetector(ast.NodeVisitor):
    """Detect calls to known async functions that are NOT awaited."""
    def __init__(self, filepath, async_func_names):
        self.filepath = filepath
        self.async_func_names = async_func_names  # set of function names
        self.issues = []  # list of (lineno, func_name, context)
        self._in_await = False
    
    def visit_Await(self, node):
        self._in_await = True
        self.generic_visit(node)
        self._in_await = False
    
    def visit_Call(self, node):
        func_name = self._get_func_name(node)
        if func_name and func_name in self.async_func_names and not self._in_await:
            # Check if this call is the value of an Await node
            # We need to check parent context
            self.issues.append((node.lineno, func_name, self._get_line(node.lineno)))
        self.generic_visit(node)
    
    def _get_func_name(self, node):
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None
    
    def _get_line(self, lineno):
        try:
            with open(self.filepath) as f:
                lines = f.readlines()
                if lineno <= len(lines):
                    return lines[lineno - 1].strip()
        except:
            pass
        return ""


class AwaitChecker(ast.NodeVisitor):
    """More accurate checker: walks AST and flags async calls not wrapped in Await."""
    def __init__(self, filepath, async_func_names):
        self.filepath = filepath
        self.async_func_names = async_func_names
        self.issues = []
        self.awaited_nodes = set()
    
    def visit_Await(self, node):
        # Mark the direct call inside await as "awaited"
        if isinstance(node.value, ast.Call):
            self.awaited_nodes.add(id(node.value))
        self.generic_visit(node)
    
    def visit_Call(self, node):
        func_name = self._get_func_name(node)
        if func_name and func_name in self.async_func_names:
            if id(node) not in self.awaited_nodes:
                line_content = self._get_line(node.lineno)
                # Filter: if asyncio.create_task wraps this, it's fine
                if "create_task" not in line_content and "ensure_future" not in line_content:
                    self.issues.append((node.lineno, func_name, line_content))
        self.generic_visit(node)

    def _get_func_name(self, node):
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None
    
    def _get_line(self, lineno):
        try:
            with open(self.filepath) as f:
                lines = f.readlines()
                if lineno <= len(lines):
                    return lines[lineno - 1].strip()
        except:
            pass
        return ""


def scan_project(root_dir):
    src_dir = Path(root_dir) / "src"
    
    # Phase 1: Collect ALL async function names across the project
    all_async_funcs = set()
    async_func_details = []  # (filepath, name, lineno, class)
    
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"  SKIP (parse error): {py_file}: {e}")
            continue
        
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                all_async_funcs.add(node.name)
                # Find class context
                class_name = None
                for parent_node in ast.walk(tree):
                    if isinstance(parent_node, ast.ClassDef):
                        for child in ast.iter_child_nodes(parent_node):
                            if child is node:
                                class_name = parent_node.name
                async_func_details.append((str(py_file), node.name, node.lineno, class_name))
    
    print(f"Found {len(all_async_funcs)} unique async function names across {len(async_func_details)} definitions\n")
    
    # Common async names that are likely false positives (stdlib/framework)
    # We'll still report them but mark separately
    framework_async = {"setup", "teardown", "on_ready", "on_message", "on_error",
                       "start", "stop", "close", "connect", "disconnect",
                       "send", "reply", "fetch", "delete", "edit",
                       "wait_for", "wait_until_ready"}
    
    # Phase 2: Scan all files for calls to async functions WITHOUT await
    print("=" * 80)
    print("MISSING AWAIT AUDIT RESULTS")
    print("=" * 80)
    
    total_issues = 0
    critical_issues = []
    
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        
        # First pass: collect awaited call node ids
        awaited_call_ids = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                awaited_call_ids.add(id(node.value))
        
        # Second pass: find calls to async funcs that are NOT awaited
        file_issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name and func_name in all_async_funcs:
                    if id(node) not in awaited_call_ids:
                        line = ""
                        try:
                            lines = source.split("\n")
                            if node.lineno <= len(lines):
                                line = lines[node.lineno - 1].strip()
                        except:
                            pass
                        
                        # Skip if wrapped in create_task or ensure_future
                        if "create_task" in line or "ensure_future" in line:
                            continue
                        
                        # Skip decorators and class definitions
                        if line.startswith("@") or line.startswith("class "):
                            continue
                            
                        # Skip if it's inside a non-async function (sync context can't await)
                        # But this is ALSO a bug - calling async from sync
                        
                        is_framework = func_name in framework_async
                        severity = "LOW " if is_framework else "HIGH"
                        
                        file_issues.append((node.lineno, func_name, line, severity))
        
        if file_issues:
            rel_path = py_file.relative_to(root_dir)
            print(f"\n📄 {rel_path}")
            for lineno, fname, line, severity in file_issues:
                marker = "⚠️ " if severity == "HIGH" else "   "
                print(f"  {marker}L{lineno}: {fname}() — {severity}")
                print(f"       {line}")
                total_issues += 1
                if severity == "HIGH":
                    critical_issues.append((str(rel_path), lineno, fname, line))
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY: {total_issues} total issues found, {len(critical_issues)} HIGH severity")
    print(f"{'=' * 80}")
    
    if critical_issues:
        print(f"\n🚨 CRITICAL ISSUES (non-framework async calls missing await):")
        for fpath, lineno, fname, line in critical_issues:
            print(f"  {fpath}:{lineno} — {fname}()")
            print(f"    {line}")
    
    return critical_issues


if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    issues = scan_project(root)
    sys.exit(1 if issues else 0)
