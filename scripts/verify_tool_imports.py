import sys
import os

# Set up path so imports work
sys.path.append(os.getcwd())

from src.tools.registry import ToolRegistry

print(f"Registry before import: {'execute_skill' in ToolRegistry._tools}")

try:
    import src.tools.skill_bridge
    print("Imported src.tools.skill_bridge")
except ImportError as e:
    print(f"Import Error: {e}")

print(f"Registry after import: {'execute_skill' in ToolRegistry._tools}")

if 'execute_skill' in ToolRegistry._tools:
    print("SUCCESS: execute_skill is registered.")
    sys.exit(0)
else:
    print("FAILURE: execute_skill not registered.")
    sys.exit(1)
