"""
Regression test: IMA autonomy loops must feed tool outputs back into
context_history so the LLM can see what its tools returned.

Root cause: autonomy.py did `response = result[0]` and discarded `result[2]`
(tool_outputs). The LLM called tools successfully but never saw the results,
causing it to loop 15 times saying "the drought persists."

Fix: tool outputs are now captured and appended to context_history as
[STEP N TOOL RESULTS] blocks.
"""
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch

from src.lobes.creative.autonomy import AutonomyAbility


class DummyCognition:
    """Returns a 3-tuple (response_text, files, tool_outputs) like real cognition."""
    def __init__(self, responses):
        self._responses = responses
        self._call_count = 0

    async def process(self, **kwargs):
        if self._call_count < len(self._responses):
            result = self._responses[self._call_count]
        else:
            result = ("<HALT>", [], [])
        self._call_count += 1
        return result


class DummyBot:
    def __init__(self, cognition):
        self.is_processing = False
        self.last_interaction = time.time() - 1000
        self.cognition = cognition
        self.dev_channel_msgs = []
        self.hippocampus = MagicMock()
        self.hippocampus.observe = AsyncMock()

    async def send_to_dev_channel(self, msg):
        self.dev_channel_msgs.append(msg)


@pytest.fixture(autouse=True)
def mock_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock) as m:
        yield m


def make_autonomy(cognition_responses):
    """Create an AutonomyAbility with fake cognition that returns tuples."""
    cognition = DummyCognition(cognition_responses)
    bot = DummyBot(cognition)
    lobe = MagicMock()
    lobe.cerebrum.bot = bot
    ability = AutonomyAbility(lobe)
    return ability, bot, cognition


class TestToolOutputFeedback:
    """Regression: Tool outputs must appear in context_history for next step."""

    @pytest.mark.asyncio
    async def test_dev_cycle_includes_tool_outputs_in_context(self):
        """Dev cycle must feed tool results back into context_history."""
        tool_output_step0 = ["Tool(read_file) Output: def hello(): pass"]

        ability, bot, cognition = make_autonomy([
            # Step 0: returns response + tool outputs
            ("I found the file, reading it now.", [], tool_output_step0),
            # Step 1: should see step 0's tool outputs
            ("Great, tests pass.", [], ["Tool(test_code) Output: 5 passed"]),
            # Step 2: halt
            ("<HALT>", [], []),
        ])

        # Capture contexts passed to process()
        captured_contexts = []
        original_process = cognition.process

        async def capturing_process(**kwargs):
            captured_contexts.append(kwargs.get("context", ""))
            return await original_process(**kwargs)

        cognition.process = capturing_process

        with patch('src.tools.weekly_quota.is_quota_met', return_value=False), \
             patch.object(ability, '_build_dev_prompt', return_value="Start dev work"):
            await ability._run_dev_work_cycle(remaining_hours=3.0)

        # Step 1's context must contain step 0's tool output
        assert len(captured_contexts) >= 2, \
            f"Expected at least 2 process calls, got {len(captured_contexts)}"

        step1_context = captured_contexts[1]
        assert "Tool(read_file) Output: def hello(): pass" in step1_context, \
            f"Step 0 tool output missing from step 1 context:\n{step1_context}"

    @pytest.mark.asyncio
    async def test_dev_cycle_works_without_tool_outputs(self):
        """Dev cycle must still work when there are no tool outputs."""
        ability, bot, _ = make_autonomy([
            ("Thinking about the problem...", [], []),
            ("<HALT>", [], []),
        ])

        with patch('src.tools.weekly_quota.is_quota_met', return_value=False), \
             patch.object(ability, '_build_dev_prompt', return_value="Start dev work"):
            await ability._run_dev_work_cycle(remaining_hours=3.0)
        # No crash = pass

    @pytest.mark.asyncio
    async def test_dev_cycle_handles_string_response(self):
        """Dev cycle must handle cognition returning a plain string (not tuple)."""
        ability, bot, cognition = make_autonomy([])

        # Override to return plain string
        async def plain_string_process(**kwargs):
            return "<HALT>"
        cognition.process = plain_string_process

        with patch('src.tools.weekly_quota.is_quota_met', return_value=False), \
             patch.object(ability, '_build_dev_prompt', return_value="Start dev work"):
            await ability._run_dev_work_cycle(remaining_hours=3.0)
        # No crash = pass
