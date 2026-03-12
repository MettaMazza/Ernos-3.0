import sys
import os
import asyncio

# Add src to path
sys.path.append(os.getcwd())

from config import settings
from src.tools.registry import ToolRegistry
# Force load support tools
import src.tools.support_tools
from src.prompts import PromptManager

async def main():
    print("--- Checking Tool Registry ---")
    tools = ToolRegistry.list_tools()
    print(f"Total entries: {len(tools)}")
    escalate = ToolRegistry.get_tool("escalate_ticket")
    if escalate:
        print(f"Found 'escalate_ticket': {escalate.name}")
    else:
        print("ERROR: 'escalate_ticket' NOT FOUND in Registry.")

    print("\n--- Checking PromptManager Manifest ---")
    pm = PromptManager()
    manifest = pm._generate_tool_manifest()
    print(f"Manifest length: {len(manifest)}")
    if "[TOOL: escalate_ticket" in manifest or "escalate_ticket" in manifest:
        print("SUCCESS: 'escalate_ticket' is in the manifest.")
        print("Preview:")
        print(manifest) # Print it all to be sure
    else:
        print("FAILURE: 'escalate_ticket' is MISSING from the manifest.")
        print("Full Manifest:")
        print(manifest)

if __name__ == "__main__":
    asyncio.run(main())
