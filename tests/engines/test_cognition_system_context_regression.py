"""
Regression test: CognitionEngine.process() must accept calls without
an explicit `system_context` argument.

Root cause: autonomy.py, gaming, daemons, and web_chat_handler all called
process() without system_context, but it was a required positional arg.

Fix: system_context now defaults to "" in the process() signature.
"""
import pytest
import inspect
from src.engines.cognition import CognitionEngine


class TestSystemContextDefault:
    """Regression: system_context must have a default value."""

    def test_system_context_has_default(self):
        """process() signature must have a default for system_context."""
        sig = inspect.signature(CognitionEngine.process)
        param = sig.parameters["system_context"]
        assert param.default is not inspect.Parameter.empty, \
            "system_context must have a default value — autonomy callers don't pass it"
        assert param.default == "", \
            f"system_context default should be '' but is {param.default!r}"

    def test_process_callable_without_system_context(self):
        """process() must be callable with just input_text and context kwargs."""
        sig = inspect.signature(CognitionEngine.process)
        # Simulate the exact kwargs autonomy.py uses (no system_context)
        kwargs = {
            "input_text": "test",
            "context": "ctx",
            "complexity": "COMPLEX",
            "request_scope": "CORE",
            "user_id": "sys",
            "skip_defenses": True,
        }
        # This should NOT raise TypeError
        try:
            bound = sig.bind(None, **kwargs)  # None = self
        except TypeError as e:
            pytest.fail(f"process() rejected autonomy-style call: {e}")
