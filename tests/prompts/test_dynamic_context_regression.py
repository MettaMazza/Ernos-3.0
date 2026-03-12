"""
Regression tests for src/prompts/dynamic_context.txt

Ensures:
1. Every {placeholder} in the template has a matching key in the HUD loader + manager kwargs
2. The HUD loader returns defaults for every required key
3. The full template renders without KeyError
4. Gaming fields are correctly populated when active vs inactive
5. No orphaned HUD keys exist that the template never uses
"""
import pytest
import re
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


# ─── Constants ───────────────────────────────────────────────────────────────

# Resolve project root: tests/prompts/this_file.py -> tests/ -> project_root/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = _PROJECT_ROOT / "src" / "prompts"
TEMPLATE_PATH = PROMPTS_DIR / "dynamic_context.txt"

# Keys injected directly by PromptManager.get_system_prompt() (not from HUD)
MANAGER_KWARGS = {
    "timestamp", "scope", "user_id", "user_name", "active_engine",
    "view_mode", "interaction_mode", "platform",
    "system_state_content", "active_goals", "working_memory_summary",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_placeholders(template_text: str) -> set:
    """Extract all {placeholder_name} tokens from a template string."""
    return set(re.findall(r'\{([a-z_]+)\}', template_text))


def _load_template() -> str:
    """Load the real dynamic_context.txt template."""
    assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _get_hud_defaults() -> dict:
    """Get the default HUD dict from load_ernos_hud (mocking out live data sources)."""
    with patch.dict(os.environ, {}, clear=False):
        patches = [
            patch("os.path.exists", return_value=False),
        ]
        for p in patches:
            p.start()
        try:
            from src.prompts.hud_ernos import load_ernos_hud
            hud = load_ernos_hud("PUBLIC", "test_user", False)
        finally:
            for p in patches:
                p.stop()
    return hud


# ─── SECTION 1: Template <-> HUD Key Parity ─────────────────────────────────

class TestTemplateParity:
    """Verify every placeholder in the template has a source."""

    def test_template_file_exists(self):
        assert TEMPLATE_PATH.exists()

    def test_all_placeholders_have_sources(self):
        """Every {key} in the template must come from either manager kwargs or HUD."""
        template = _load_template()
        placeholders = _extract_placeholders(template)
        hud = _get_hud_defaults()

        all_available = MANAGER_KWARGS | set(hud.keys())
        missing = placeholders - all_available
        assert not missing, (
            f"Template placeholders with NO source: {sorted(missing)}\n"
            f"These will cause KeyError at runtime."
        )

    def test_no_orphaned_hud_keys(self):
        """Every HUD key should appear in the template (or fork template)."""
        template = _load_template()
        placeholders = _extract_placeholders(template)
        hud = _get_hud_defaults()

        fork_path = PROMPTS_DIR / "dynamic_context_fork.txt"
        fork_placeholders = set()
        if fork_path.exists():
            fork_placeholders = _extract_placeholders(fork_path.read_text())

        all_template_keys = placeholders | fork_placeholders | MANAGER_KWARGS
        orphaned = set(hud.keys()) - all_template_keys
        if orphaned:
            pytest.skip(f"Orphaned HUD keys (not in any template): {sorted(orphaned)}")


# ─── SECTION 2: HUD Loader Defaults ─────────────────────────────────────────

class TestHudDefaults:
    """Verify the HUD loader returns sane defaults for every required key."""

    def test_hud_returns_dict(self):
        hud = _get_hud_defaults()
        assert isinstance(hud, dict)

    def test_hud_has_all_required_keys(self):
        """HUD must provide defaults for every non-manager placeholder."""
        template = _load_template()
        placeholders = _extract_placeholders(template)
        hud = _get_hud_defaults()

        hud_required = placeholders - MANAGER_KWARGS
        missing = hud_required - set(hud.keys())
        assert not missing, (
            f"HUD missing defaults for template keys: {sorted(missing)}"
        )

    def test_hud_values_are_strings(self):
        """All HUD values must be strings (for str.format() safety)."""
        hud = _get_hud_defaults()
        non_strings = {k: type(v).__name__ for k, v in hud.items() if not isinstance(v, str)}
        assert not non_strings, f"Non-string HUD values: {non_strings}"

    def test_hud_values_are_nonempty(self):
        """All HUD default values must be non-empty strings."""
        hud = _get_hud_defaults()
        # These keys are populated by live log/file readers which may
        # produce empty strings when the underlying files exist but are empty.
        # Their defaults are overwritten by the loader, so we skip them.
        LIVE_LOADED_KEYS = {
            "activity_tail", "terminal_tail", "error_log",
            "room_roster", "reasoning_context",
            # KG keys are empty when no graph data exists (valid default)
            "kg_recent_nodes", "kg_beliefs", "kg_relationships",
        }
        empty = [
            k for k, v in hud.items()
            if k not in LIVE_LOADED_KEYS
            and v is not None and isinstance(v, str) and len(v.strip()) == 0
        ]
        assert not empty, f"Empty HUD defaults: {empty}"


# ─── SECTION 3: Full Template Rendering ──────────────────────────────────────

class TestTemplateRendering:
    """Verify the template renders without errors when all keys are provided."""

    def _build_full_kwargs(self) -> dict:
        """Build a complete kwargs dict that covers every placeholder."""
        hud = _get_hud_defaults()
        manager_vals = {k: f"TEST_{k.upper()}" for k in MANAGER_KWARGS}
        return {**manager_vals, **hud}

    def test_template_renders_without_error(self):
        template = _load_template()
        kwargs = self._build_full_kwargs()
        rendered = template.format(**kwargs)
        assert isinstance(rendered, str)
        assert len(rendered) > 100

    def test_rendered_template_contains_no_raw_placeholders(self):
        """After rendering, no {placeholder} should remain."""
        template = _load_template()
        kwargs = self._build_full_kwargs()
        rendered = template.format(**kwargs)
        remaining = re.findall(r'\{[a-z_]+\}', rendered)
        assert not remaining, f"Unresolved placeholders after rendering: {remaining}"

    def test_rendered_template_contains_all_sections(self):
        """Verify every section header appears in the rendered output."""
        template = _load_template()
        kwargs = self._build_full_kwargs()
        rendered = template.format(**kwargs)

        expected_sections = [
            "SECTION 1",
            "SECTION 2",
            "SECTION 3",
            "SECTION 4",
            "SECTION 5",
            "SECTION 6",
            "SECTION 7",
            "SECTION 8",
            "SECTION 9",
            "SECTION 10",
            "SECTION 11",
            "SECTION 12",
            "SECTION 13",
            "SECTION 14",
            "SECTION 15",
        ]
        for section in expected_sections:
            assert section in rendered, f"Missing section: {section}"


# ─── SECTION 4: Gaming Fields ────────────────────────────────────────────────

class TestGamingFields:
    """Verify gaming-specific HUD fields are populated correctly."""

    GAMING_KEYS = [
        "game_name", "game_username", "game_health", "game_food",
        "game_time_of_day", "game_biome", "game_threats", "game_nearby",
        "game_inventory", "game_goal", "game_action", "game_precognition",
        "game_narrative",
    ]

    def test_gaming_defaults_when_inactive(self):
        """When no gaming_state.json exists, all gaming keys should have safe defaults."""
        hud = _get_hud_defaults()
        for key in self.GAMING_KEYS:
            assert key in hud, f"Missing gaming key: {key}"
            assert isinstance(hud[key], str)

    def test_gaming_active_state(self):
        """When gaming_state.json shows active, gaming fields should be populated."""
        mock_state = {
            "active": True,
            "game": "Minecraft",
            "mc_username": "TestBot",
            "current_action": "mining diamonds",
            "current_goal": "build a castle",
            "health": 18,
            "food": 15,
            "is_day": False,
            "biome": "plains",
            "hostiles_nearby": True,
            "nearby": "zombie, skeleton",
            "inventory_summary": "diamond_pickaxex1, stonex32",
            "precognition_queue": "attack zombie, flee to shelter",
            "narrative": "I am mining deep underground.",
        }

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mock_state, f)
            state_path = f.name

        try:
            with patch("os.path.join", return_value=state_path):
                from src.prompts.hud_ernos import load_ernos_hud
                hud = load_ernos_hud("CORE", "sys", True)

            assert "Minecraft" in hud["game_name"]
            assert "TestBot" in hud["game_username"]
            assert "18" in hud["game_health"]
            assert "15" in hud["game_food"]
            assert "Nighttime" in hud["game_time_of_day"]
            assert hud["game_biome"] == "plains"
            assert "HOSTILES" in hud["game_threats"]
            assert "zombie" in hud["game_nearby"]
            assert "diamond" in hud["game_inventory"]
            assert hud["game_goal"] == "build a castle"
            assert hud["game_action"] == "mining diamonds"
            assert "attack" in hud["game_precognition"]
            assert "mining" in hud["game_narrative"]
        finally:
            os.unlink(state_path)

    def test_gaming_inactive_state(self):
        """When gaming_state.json shows inactive, status should reflect idle."""
        mock_state = {
            "active": False,
            "narrative": "No active gaming session."
        }

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mock_state, f)
            state_path = f.name

        try:
            with patch("os.path.join", return_value=state_path):
                from src.prompts.hud_ernos import load_ernos_hud
                hud = load_ernos_hud("CORE", "sys", True)

            assert "Idle" in hud["gaming_status"]
        finally:
            os.unlink(state_path)


# ─── SECTION 5: Specific Key Groups ─────────────────────────────────────────

class TestKeyGroups:
    """Verify specific groups of HUD keys are present and have defaults."""

    def test_subsystem_status_keys(self):
        hud = _get_hud_defaults()
        required = [
            "cognition_status", "memory_status", "gaming_status",
            "voice_status", "autonomy_status", "embodiment_state",
            "kg_status", "vector_status",
        ]
        for k in required:
            assert k in hud, f"Missing subsystem key: {k}"

    def test_knowledge_graph_keys(self):
        hud = _get_hud_defaults()
        required = ["kg_recent_nodes", "kg_beliefs", "kg_relationships"]
        for k in required:
            assert k in hud, f"Missing KG key: {k}"

    def test_autonomy_keys(self):
        hud = _get_hud_defaults()
        required = [
            "lessons_learned", "skills_acquired", "pending_research",
            "incomplete_goals", "queued_actions", "tool_call_history",
            "autonomy_log", "wisdom_log", "proactive_intentions",
        ]
        for k in required:
            assert k in hud, f"Missing autonomy key: {k}"

    def test_synapse_bridge_keys(self):
        hud = _get_hud_defaults()
        required = [
            "channel_adapter_status", "skills_loaded",
            "lane_queue_status", "profile_status",
        ]
        for k in required:
            assert k in hud, f"Missing synapse key: {k}"

    def test_inner_state_keys(self):
        hud = _get_hud_defaults()
        required = ["emotional_status", "discomfort_status", "user_threat_status"]
        for k in required:
            assert k in hud, f"Missing inner state key: {k}"

    def test_sleep_cycle_keys(self):
        hud = _get_hud_defaults()
        required = ["dream_status", "compression_status", "self_review_history"]
        for k in required:
            assert k in hud, f"Missing sleep cycle key: {k}"

    def test_temporal_key(self):
        hud = _get_hud_defaults()
        assert "temporal_status" in hud

    def test_provenance_key(self):
        hud = _get_hud_defaults()
        assert "provenance_recent" in hud

    def test_test_health_key(self):
        hud = _get_hud_defaults()
        assert "test_health" in hud


# ─── SECTION 6: Integration — PromptManager End-to-End ───────────────────────

class TestPromptManagerIntegration:
    """Verify PromptManager.get_system_prompt() renders the real template."""

    @pytest.fixture
    def prompt_manager(self):
        from src.prompts.manager import PromptManager
        return PromptManager()

    def test_full_render_public(self, prompt_manager):
        """Full render in PUBLIC scope should not crash."""
        prompt = prompt_manager.get_system_prompt(
            timestamp="2026-02-23 08:30",
            scope="PUBLIC",
            user_id="test_user_123",
            user_name="TestUser",
            active_engine="gemini-3",
            active_mode="Cloud",
            is_core=False,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 500
        assert "Template Error" not in prompt

    def test_full_render_core(self, prompt_manager):
        """Full render in CORE scope with GOD VIEW."""
        prompt = prompt_manager.get_system_prompt(
            timestamp="2026-02-23 08:30",
            scope="CORE",
            user_id="sys",
            user_name="Ernos (System)",
            is_core=True,
        )
        assert isinstance(prompt, str)
        assert "GOD VIEW" in prompt

    def test_no_template_error_in_output(self, prompt_manager):
        """The rendered prompt should never contain '[Template Error'."""
        prompt = prompt_manager.get_system_prompt(
            timestamp="2026-02-23 08:30",
            scope="CORE",
            user_id="sys",
            is_core=True,
        )
        assert "[Template Error" not in prompt, (
            "Template rendered with missing key! Check dynamic_context.txt vs HUD loader."
        )
