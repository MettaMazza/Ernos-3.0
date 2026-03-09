"""
Tool Registry.
Centralized registration for AI capabilities.
"""
import logging
import inspect
from typing import Callable, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger("ToolRegistry")

# Common parameter aliases that the AI might use incorrectly
# Maps: wrong_name -> correct_name
PARAM_ALIASES = {
    # Query variants
    "question": "problem",      # deep_think
    "query": "instruction",     # consult_curator, consult_ontologist
    "search": "query",          # search_web
    "topic": "query",           # consult_world_lobe
    
    # Path variants  
    "filepath": "path",         # read_file_page, search_codebase
    "file_path": "path",
    "directory": "path",
    "dir": "path",
    
    # Content variants
    "message": "content",       # publish_to_bridge
    "text": "content",
    "content": "code",          # create_program
    
    # Coding variants
    "action": "mode",           # create_program
    
    # Line range variants
    "start": "start_line",      # read_file_page
    "end": "limit",
    "lines": "limit",
    
    # Ontologist specific
    "instruction": None,        # Special case: ontologist rejects instruction, needs subject/predicate/object
}

@dataclass
class ToolDefinition:
    name: str
    func: Callable
    description: str
    parameters: Dict[str, Any]

class ToolRegistry:
    _tools: Dict[str, ToolDefinition] = {}

    @classmethod
    def register(cls, name: str = None, description: str = None):
        """Decorator to register a tool."""
        def decorator(func):
            tool_name = name or func.__name__
            doc = description or func.__doc__ or "No description."
            
            # Simple parameter inspection (can be enhanced with Pydantic)
            sig = inspect.signature(func)
            params = {
                k: str(v.annotation) 
                for k, v in sig.parameters.items() 
                if not k.startswith("_") and k != "self" and k != "cls"
            }

            definition = ToolDefinition(
                name=tool_name,
                func=func,
                description=doc,
                parameters=params
            )
            
            cls._tools[tool_name] = definition
            # logger.info(f"Tool Registered: {tool_name}")
            return func
        return decorator

    @classmethod
    def get_tool(cls, name: str) -> ToolDefinition:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[ToolDefinition]:
        return list(cls._tools.values())
    
    @classmethod
    def _correct_params(cls, tool_name: str, kwargs: dict, params: dict) -> dict:
        """
        INTERCEPTOR: Auto-correct common parameter naming mistakes.
        Maps aliases to actual parameter names before execution.
        """
        corrected = {}
        corrections_made = []
        
        for key, value in kwargs.items():
            # Check if this key is a known alias AND the tool doesn't accept it
            if key in PARAM_ALIASES and key not in params:
                correct_key = PARAM_ALIASES[key]
                
                # Special case: ontologist shouldn't receive 'instruction' at all
                if key == "instruction" and tool_name == "consult_ontologist":
                    logger.warning(f"[Interceptor] Dropping 'instruction' for ontologist - use subject/predicate/object")
                    continue
                    
                if correct_key and correct_key in params:
                    corrected[correct_key] = value
                    corrections_made.append(f"{key} -> {correct_key}")
                else:
                    corrected[key] = value
            else:
                corrected[key] = value
        
        if corrections_made:
            logger.info(f"[Interceptor] Corrected params for {tool_name}: {', '.join(corrections_made)}")
        
        return corrected
    
    @classmethod
    async def execute(cls, tool_name: str, *args, request_scope=None, user_id=None, bot=None, channel=None, **kwargs):
        """Execute a registered tool with Context Injection and Parameter Correction."""
        tool = cls._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found.")
        
        # Get tool's actual parameters
        sig = inspect.signature(tool.func)
        params = sig.parameters
        
        # INTERCEPTOR: Correct parameter names before binding
        kwargs = cls._correct_params(tool_name, kwargs, params)
        
        # Safety: Strip unknown kwargs for tools without **kwargs
        # This MUST happen BEFORE bind_partial to prevent 'unexpected keyword argument' crashes
        has_var_keyword = any(p.kind == p.VAR_KEYWORD for p in params.values())
        if not has_var_keyword:
            accepted = set(params.keys())
            unknown = [k for k in kwargs if k not in accepted]
            if unknown:
                logger.debug(f"[Interceptor] Stripping unknown params for {tool_name}: {unknown}")
                for k in unknown:
                    del kwargs[k]
        
        # Context Injection: Only pass if tool accepts them and not already provided
        bound_args = sig.bind_partial(*args, **kwargs)
        provided_args = bound_args.arguments

        injectable = {}
        
        # Inject Request Scope
        if request_scope:
            target_param = 'request_scope'
            if 'scope' in params and 'request_scope' not in params:
                target_param = 'scope'
            
            # Check acceptance and existence
            if (target_param in params or has_var_keyword) and target_param not in provided_args:
                 injectable[target_param] = request_scope

        # Inject User ID — use `is not None` to avoid dropping user_id=0
        if user_id is not None:
            # Check acceptance and existence
            if ('user_id' in params or has_var_keyword) and 'user_id' not in provided_args:
                 injectable['user_id'] = user_id

        # Inject Bot context (for gaming/interactive tools)
        if bot:
            if ('bot' in params or has_var_keyword) and 'bot' not in provided_args:
                injectable['bot'] = bot
        
        # Inject Channel context (for gaming/interactive tools)
        if channel:
            if ('channel' in params or has_var_keyword) and 'channel' not in provided_args:
                injectable['channel'] = channel

        # Merge injection
        kwargs.update(injectable)
        
        # Handle async vs sync
        if inspect.iscoroutinefunction(tool.func):
            return await tool.func(*args, **kwargs)
    
        else:
            # Wrap synchronous tools in executor to prevent blocking the Event Loop
            import asyncio
            import functools
            loop = asyncio.get_running_loop()
            # run_in_executor does not accept kwargs directly, use partial
            func = functools.partial(tool.func, *args, **kwargs)
            return await loop.run_in_executor(None, func)

# Force load tools to trigger registration
import src.tools.browser
import src.tools.document
import src.tools.context_retrieval
import src.tools.chat_tools
import src.tools.support_tools
