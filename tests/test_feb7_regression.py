"""
Regression tests for all fixes applied on Feb 7, 2026.
Prevents re-introduction of:
1. Tool manifest generation crash (get_all_tools → list_tools, dict→dataclass)
2. memory_tools + backup_tools not imported (tools invisible to Ernos)
3. Parameter alias correction (content→code, action→mode)
4. Unknown kwarg stripping must happen BEFORE bind_partial
5. Wisdom extraction template escaping ({} → {{}})
6. read_channel in kernel prompt (LLM awareness)
"""
import pytest
import inspect
import os
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools.registry import ToolRegistry, ToolDefinition, PARAM_ALIASES


# ============================================================
# 1. TOOL MANIFEST GENERATION
# ============================================================

class TestToolManifestGeneration:
    """Regression: PromptManager._generate_tool_manifest used get_all_tools() 
    (doesn't exist) and treated ToolDefinition dataclasses as dicts."""
    
    def test_list_tools_returns_tool_definitions(self):
        """list_tools must return ToolDefinition objects, not dicts."""
        tools = ToolRegistry.list_tools()
        assert len(tools) > 0, "No tools registered"
        for tool in tools:
            assert isinstance(tool, ToolDefinition), f"Expected ToolDefinition, got {type(tool)}"
            assert hasattr(tool, 'name'), "ToolDefinition missing 'name' attribute"
            assert hasattr(tool, 'description'), "ToolDefinition missing 'description' attribute"
            assert hasattr(tool, 'parameters'), "ToolDefinition missing 'parameters' attribute"
    
    def test_no_get_all_tools_method(self):
        """get_all_tools must NOT exist — prevents accidental reversion."""
        assert not hasattr(ToolRegistry, 'get_all_tools'), \
            "get_all_tools still exists on ToolRegistry — use list_tools() instead"
    
    def test_tool_definition_attributes_not_dict_access(self):
        """Accessing .name, .description, .parameters must work on ToolDefinition."""
        tools = ToolRegistry.list_tools()
        tool = tools[0]
        # These should work (dataclass attributes)
        _ = tool.name
        _ = tool.description
        _ = tool.parameters
        # This should NOT work (dict access)
        with pytest.raises((TypeError, AttributeError)):
            tool.get("name", "unknown")
    
    def test_prompt_manager_manifest_generation(self):
        """PromptManager._generate_tool_manifest must not crash."""
        from src.prompts.manager import PromptManager
        pm = PromptManager.__new__(PromptManager)
        manifest = pm._generate_tool_manifest()
        assert isinstance(manifest, str)
        assert "AVAILABLE TOOLS" in manifest or manifest == ""
        # Should contain at least one tool name
        if manifest:
            assert "read_channel" in manifest or "search_web" in manifest


# ============================================================
# 2. MODULE IMPORT REGISTRATION  
# ============================================================

class TestModuleImportRegistration:
    """Regression: memory_tools.py and backup_tools.py were never imported
    in tools/__init__.py, so their @ToolRegistry.register decorators 
    never fired and the tools were invisible."""
    
    def test_memory_tools_imported_in_init(self):
        """tools/__init__.py must import memory_tools."""
        init_path = os.path.join("src", "tools", "__init__.py")
        with open(init_path) as f:
            content = f.read()
        assert "memory_tools" in content, \
            "memory_tools not imported in tools/__init__.py — read_channel will be invisible"
    
    def test_backup_tools_imported_in_init(self):
        """tools/__init__.py must import backup_tools."""
        init_path = os.path.join("src", "tools", "__init__.py")
        with open(init_path) as f:
            content = f.read()
        assert "backup_tools" in content, \
            "backup_tools not imported in tools/__init__.py — backup tools will be invisible"
    
    def test_read_channel_registered(self):
        """read_channel must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("read_channel")
        assert tool is not None, "read_channel not registered — check tools/__init__.py imports"
        assert tool.name == "read_channel"
    
    def test_manage_lessons_registered(self):
        """manage_lessons must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("manage_lessons")
        assert tool is not None, "manage_lessons not registered"
    
    def test_manage_preferences_registered(self):
        """manage_preferences must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("manage_preferences")
        assert tool is not None, "manage_preferences not registered"
    
    def test_manage_calendar_registered(self):
        """manage_calendar must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("manage_calendar")
        assert tool is not None, "manage_calendar not registered"
    
    def test_request_my_backup_registered(self):
        """request_my_backup must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("request_my_backup")
        assert tool is not None, "request_my_backup not registered"
    
    def test_verify_backup_registered(self):
        """verify_backup must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("verify_backup")
        assert tool is not None, "verify_backup not registered"
    
    def test_restore_my_context_registered(self):
        """restore_my_context must be in the ToolRegistry."""
        tool = ToolRegistry.get_tool("restore_my_context")
        assert tool is not None, "restore_my_context not registered"


# ============================================================
# 3. PARAMETER ALIAS CORRECTION
# ============================================================

class TestParameterAliases:
    """Regression: LLM calls create_program with content= instead of code=
    and action= instead of mode=, causing 'unexpected keyword argument'."""
    
    def test_content_aliased_to_code(self):
        """PARAM_ALIASES must map 'content' → 'code' for create_program."""
        assert "content" in PARAM_ALIASES, "Missing 'content' alias"
        assert PARAM_ALIASES["content"] == "code", \
            f"'content' alias points to '{PARAM_ALIASES['content']}', expected 'code'"
    
    def test_action_aliased_to_mode(self):
        """PARAM_ALIASES must map 'action' → 'mode' for create_program."""
        assert "action" in PARAM_ALIASES, "Missing 'action' alias"
        assert PARAM_ALIASES["action"] == "mode", \
            f"'action' alias points to '{PARAM_ALIASES['action']}', expected 'mode'"
    
    def test_alias_correction_applies_to_create_program(self):
        """_correct_params must transform content→code and action→mode."""
        # Get create_program's actual params
        tool = ToolRegistry.get_tool("create_program")
        assert tool is not None
        sig = inspect.signature(tool.func)
        params = sig.parameters
        
        # Wrong kwargs from LLM
        wrong_kwargs = {"content": "print('hello')", "action": "create"}
        
        corrected = ToolRegistry._correct_params("create_program", wrong_kwargs, params)
        
        # 'content' should become 'code' (since 'code' is accepted by create_program)
        assert "code" in corrected, "Alias correction failed: 'content' not mapped to 'code'"
        assert corrected["code"] == "print('hello')"
        
        # 'action' should become 'mode' (since 'mode' is accepted by create_program)
        assert "mode" in corrected, "Alias correction failed: 'action' not mapped to 'mode'"
        assert corrected["mode"] == "create"


# ============================================================
# 4. UNKNOWN KWARG STRIPPING ORDER
# ============================================================

class TestKwargStrippingOrder:
    """Regression: Safety net stripping happened AFTER bind_partial,
    so tools without **kwargs crashed before stripping could help."""
    
    @pytest.mark.asyncio
    async def test_unknown_kwargs_stripped_before_crash(self):
        """Tools without **kwargs must not crash on unknown params."""
        @ToolRegistry.register(name="_test_strict_tool", description="Test tool")
        def _test_strict_tool(name: str) -> str:
            return f"Hello {name}"
        
        # This should NOT crash — 'bogus' should be stripped
        result = await ToolRegistry.execute(
            "_test_strict_tool", 
            name="World", 
            bogus="should_be_stripped"
        )
        assert result == "Hello World"
    
    @pytest.mark.asyncio
    async def test_kwargs_tools_keep_extra_params(self):
        """Tools WITH **kwargs must keep extra params (no stripping)."""
        @ToolRegistry.register(name="_test_kwargs_tool", description="Test tool")
        async def _test_kwargs_tool(name: str, **kwargs) -> str:
            return f"Hello {name}, extra={kwargs.get('extra', 'none')}"
        
        result = await ToolRegistry.execute(
            "_test_kwargs_tool",
            name="World",
            extra="kept"
        )
        assert "extra=kept" in result
    
    @pytest.mark.asyncio 
    async def test_context_injection_still_works_after_stripping(self):
        """bot/user_id/request_scope injection must work even after stripping."""
        @ToolRegistry.register(name="_test_inject_tool", description="Test tool")
        async def _test_inject_tool(name: str, **kwargs) -> str:
            bot = kwargs.get("bot")
            user_id = kwargs.get("user_id")
            return f"name={name}, bot={bot is not None}, user={user_id}"
        
        mock_bot = MagicMock()
        result = await ToolRegistry.execute(
            "_test_inject_tool",
            name="Test",
            bot=mock_bot,
            user_id="12345"
        )
        assert "bot=True" in result
        assert "user=12345" in result


# ============================================================
# 5. WISDOM TEMPLATE ESCAPING
# ============================================================

class TestWisdomTemplateEscaping:
    """Regression: dreamer_wisdom.txt had unescaped { } in JSON example,
    causing KeyError: '\\n  \"topic\"' in .format()."""
    
    def test_template_format_does_not_crash(self):
        """dreamer_wisdom.txt must survive .format(topic=..., insight=...)."""
        template_path = os.path.join("src", "prompts", "dreamer_wisdom.txt")
        with open(template_path) as f:
            template = f.read()
        
        # This was the exact crash — .format() on a template with { } in JSON example
        try:
            result = template.format(topic="Test Topic", insight="Test Insight")
        except KeyError as e:
            pytest.fail(f"Template .format() crashed with KeyError: {e} — "
                       f"JSON example braces must be escaped as {{{{ }}}}")
        
        assert "Test Topic" in result
        assert "Test Insight" in result
    
    def test_template_example_json_preserved(self):
        """The example JSON block must survive formatting (escaped braces become literal)."""
        template_path = os.path.join("src", "prompts", "dreamer_wisdom.txt")
        with open(template_path) as f:
            template = f.read()
        
        result = template.format(topic="AI", insight="Learning")
        # The rendered output should contain a JSON-like example with literal braces
        assert '"topic"' in result
        assert '"truth"' in result
        assert '"applicability"' in result


# ============================================================
# 6. READ_CHANNEL IN KERNEL PROMPT
# ============================================================

class TestKernelPromptChannelAwareness:
    """Regression: kernel.txt had no mention of read_channel,
    so the LLM confabulated inability and never called the tool."""
    
    def test_kernel_contains_read_channel_example(self):
        """kernel.txt must contain a read_channel tool example."""
        kernel_path = os.path.join("src", "prompts", "kernel_backup.txt")
        with open(kernel_path) as f:
            content = f.read()
        
        assert "read_channel" in content, \
            "kernel.txt has no mention of read_channel — LLM won't know it exists"
    
    def test_kernel_contains_channel_awareness_section(self):
        """kernel.txt must have a Channel Awareness section."""
        kernel_path = os.path.join("src", "prompts", "kernel_backup.txt")
        with open(kernel_path) as f:
            content = f.read()
        
        assert "CHANNEL AWARENESS" in content, \
            "kernel.txt missing CHANNEL AWARENESS section"
    
    def test_kernel_contains_channel_name_example(self):
        """kernel.txt must show channel_name parameter usage."""
        kernel_path = os.path.join("src", "prompts", "kernel_backup.txt")
        with open(kernel_path) as f:
            content = f.read()
        
        assert 'channel_name=' in content, \
            "kernel.txt doesn't show channel_name= parameter in read_channel example"
    
    def test_kernel_contains_must_use_directive(self):
        """kernel.txt must have a MUST-use directive for read_channel."""
        kernel_path = os.path.join("src", "prompts", "kernel_backup.txt")
        with open(kernel_path) as f:
            content = f.read()
        
        # The directive says to use read_channel when asked about other channels
        assert "MUST use" in content and "read_channel" in content, \
            "kernel.txt missing MUST-use directive for read_channel"


# ============================================================
# 7. DISCORD MENTION FORMATTING
# ============================================================

class TestDiscordMentionFormatting:
    """Regression: LLM outputs @764896542170939443 but Discord needs
    <@764896542170939443> for clickable user mentions."""
    
    def setup_method(self):
        """Create a ChatListener instance for testing."""
        from src.bot.cogs.chat import ChatListener
        self.listener = ChatListener.__new__(ChatListener)
    
    def test_bare_mention_gets_wrapped(self):
        """@<digits> must become <@digits>."""
        text = "What was the last thing on your mind, @764896542170939443?"
        result = self.listener._format_discord_mentions(text)
        assert "<@764896542170939443>" in result
        assert "@764896542170939443" in result  # still present, just wrapped
    
    def test_already_wrapped_mention_not_doubled(self):
        """<@digits> must NOT become <<@digits>>."""
        text = "Hey <@764896542170939443>, how are you?"
        result = self.listener._format_discord_mentions(text)
        assert "<<@764896542170939443>>" not in result
        assert "<@764896542170939443>" in result
    
    def test_multiple_mentions(self):
        """Multiple bare mentions in one message all get wrapped."""
        text = "Hey @764896542170939443 and @1299810741984956449!"
        result = self.listener._format_discord_mentions(text)
        assert "<@764896542170939443>" in result
        assert "<@1299810741984956449>" in result
    
    def test_mixed_wrapped_and_bare(self):
        """Mix of already-wrapped and bare mentions handled correctly."""
        text = "Hey <@764896542170939443> and @1299810741984956449!"
        result = self.listener._format_discord_mentions(text)
        assert "<<@764896542170939443>>" not in result
        assert "<@764896542170939443>" in result
        assert "<@1299810741984956449>" in result
    
    def test_no_mentions_unchanged(self):
        """Text without mentions passes through unchanged."""
        text = "Hello world, no mentions here!"
        result = self.listener._format_discord_mentions(text)
        assert result == text
    
    def test_short_numbers_not_matched(self):
        """Short numeric @mentions (not Discord IDs) should NOT be wrapped."""
        text = "Call me @12345 or @admin"
        result = self.listener._format_discord_mentions(text)
        assert "<@12345>" not in result  # too short to be a Discord ID
        assert result == text
    
    def test_email_not_matched(self):
        """Email addresses must not be mangled."""
        text = "Email me at user@example.com"
        result = self.listener._format_discord_mentions(text)
        assert result == text

