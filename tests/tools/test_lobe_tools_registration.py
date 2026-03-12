"""
Regression tests for lobe tool registration.
Ensures all expected lobe tools are properly registered.
"""
import pytest
from src.tools.registry import ToolRegistry


def test_all_lobe_tools_registered():
    """Verify all expected lobe consultation tools exist."""
    expected_tools = [
        "consult_gardener_lobe",
        "consult_architect_lobe",
        "consult_planning_lobe",  # Alias for architect
        "consult_project_lead",
        "consult_science_lobe",
        "consult_bridge_lobe",
        "consult_predictor",
        "consult_performance_lobe",
        "consult_superego",
        "consult_skeptic",
        "consult_autonomy",
        "consult_curiosity",
        "consult_journalist_lobe",
        "consult_curator",
        "consult_librarian",
        "consult_ontologist",
        "consult_social_lobe",
        "consult_subconscious",
        "consult_world_lobe",
    ]
    
    for tool in expected_tools:
        assert tool in ToolRegistry._tools, f"Tool '{tool}' is not registered"


def test_planning_lobe_is_alias_for_architect():
    """Verify planning lobe delegates to architect lobe."""
    planning_tool = ToolRegistry._tools.get("consult_planning_lobe")
    assert planning_tool is not None
    assert "planning" in planning_tool.description.lower()
