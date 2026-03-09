import logging
import asyncio
from src.tools.registry import ToolRegistry
from src.prompts import PromptManager

logger = logging.getLogger("Agents.Base")

class BaseAgent:
    """
    The genetic ancestor for all agents.
    Enforces the "Trinity Stack" (Unification of Identity) and Shared Tool Access.
    """
    def __init__(self, bot):
        self.bot = bot
        self.prompt_manager = PromptManager(prompt_dir="src/prompts")

    def get_system_prompt(self, **kwargs) -> str:
        """
        Retrieves the Unified System Prompt (Kernel + Architecture + Identity).
        Injects the Trinity of Truth into every agent.
        """
        return self.prompt_manager.get_system_prompt(**kwargs)

    async def call_tool(self, tool_name: str, **kwargs):
        """
        Unified interface for tool execution.
        Allows any agent to use any registered tool.
        """
        try:
            return await ToolRegistry.execute(tool_name, **kwargs)
        except Exception as e:
            logger.error(f"Tool execution failed ({tool_name}): {e}")
            return f"Error: {e}"
