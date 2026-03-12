"""
CognitionTracker — Live-updating Discord embed for cognition visibility.

Posts a single embed when processing starts, edits it as tools fire,
and deletes it before the final response is delivered.

This gives users real-time feedback on what Ernos is doing — like
Claude's "Thinking..." but showing actual actions.
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("Engine.CognitionTracker")

# Human-readable labels for tool names
TOOL_LABELS = {
    # Research
    "search_web": "🔍 Searching the web",
    "browse_site": "🌐 Reading webpage",
    "start_deep_research": "📚 Starting deep research",
    # Lobes
    "consult_science_lobe": "🔬 Consulting Science Lobe",
    "consult_world_lobe": "🌍 Consulting World Lobe",
    "consult_journalist_lobe": "📰 Consulting Journalist Lobe",
    "consult_architect_lobe": "🏗️ Consulting Architect Lobe",
    "consult_skeptic": "🧐 Running Skeptic Audit",
    "consult_subconscious": "💭 Consulting Subconscious",
    "consult_ima": "🪞 Consulting IMA",
    "consult_curator": "🗂️ Consulting Curator",
    "consult_ontologist": "🕸️ Consulting Ontologist",
    "consult_gardener_lobe": "🌱 Consulting Gardener",
    "consult_social_lobe": "🗣️ Consulting Social Lobe",
    "consult_project_lead": "📋 Consulting Project Lead",
    "deep_think": "🧠 Deep thinking",
    # Creative
    "generate_image": "🎨 Generating image",
    "generate_speech": "🗣️ Generating speech",
    # Documents
    "start_document": "📄 Starting document",
    "add_section": "📝 Writing section",
    "render_document": "📄 Rendering document",
    "generate_pdf": "📄 Generating PDF",
    # Agents
    "spawn_research_swarm": "🧠 Spawning research swarm",
    "delegate_to_agents": "🤖 Deploying sub-agents",
    "execute_agent_plan": "📋 Executing agent plan",
    "spawn_competitive_agents": "🏁 Racing competitive agents",
    # Memory
    "recall_user": "💾 Recalling user context",
    "search_context_logs": "🔎 Searching context logs",
    "search_memory": "🧠 Searching memory",
    "introspect": "🔍 Introspecting claim",
    "read_autobiography": "📖 Reading autobiography",
    "working_memory": "🧠 Accessing working memory",
    # Code
    "search_codebase": "💻 Searching codebase",
    "read_file": "📂 Reading file",
    "read_file_page": "📂 Reading file",
    "ingest_file": "📂 Ingesting file",
    "create_program": "⌨️ Writing code",
    # Other
    "check_world_news": "📰 Checking world news",
    "read_channel": "💬 Reading channel",
    "execute_skill": "⚡ Executing skill",
    "read_public_bridge": "🌉 Reading public bridge",
    "escalate_ticket": "🎫 Escalating ticket",
    "schedule_event": "📅 Scheduling event",
    "list_schedules": "📅 Listing schedules",
}


class CognitionTracker:
    """
    Live-updating Discord embed that shows cognition progress.

    Usage:
        tracker = CognitionTracker(channel)
        await tracker.start()
        await tracker.update("search_web")       # tool about to run
        await tracker.tool_complete("search_web") # tool finished
        await tracker.finalize()                  # delete embed
    """

    # Minimum interval between Discord message edits (seconds)
    EDIT_DEBOUNCE = 0.8

    def __init__(self, channel):
        self.channel = channel
        self._message = None  # The Discord message object
        self._status_lines: list[str] = []
        self._current_action: str = ""
        self._step_count: int = 0
        self._tool_count: int = 0
        self._start_time: float = 0
        self._last_edit: float = 0
        self._pending_update: bool = False
        self._update_lock = asyncio.Lock()
        self._agent_states: dict[str, tuple[str, str]] = {}  # agent_id -> (topic, status_emoji)
        self._deferred_task: Optional[asyncio.Task] = None

    async def start(self):
        """Post the initial status embed."""
        try:
            import discord
            self._start_time = time.time()
            embed = discord.Embed(
                description="```\n⏳ Processing...\n```",
                color=0x5865F2,  # Discord blurple
            )
            self._message = await self.channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"CognitionTracker.start failed (non-fatal): {e}")
            self._message = None

    async def update(self, tool_name_or_status: str, detail: str = None):
        """
        Update the status embed with what's happening now.

        Args:
            tool_name_or_status: Either a registered tool name (mapped to label)
                                 or a raw status string.
            detail: Optional extra detail (e.g., search query).
        """
        if not self._message:
            return

        label = TOOL_LABELS.get(tool_name_or_status, tool_name_or_status)
        if detail:
            label = f"{label}: {detail[:80]}"

        self._current_action = label
        self._pending_update = True
        await self._flush()

    async def tool_complete(self, tool_name: str):
        """Record a tool as completed and update the embed."""
        if not self._message:
            return

        label = TOOL_LABELS.get(tool_name, f"⚙️ {tool_name}")
        self._status_lines.append(label)
        self._tool_count += 1
        self._current_action = ""
        self._pending_update = True
        await self._flush()

    async def update_step(self, step: int):
        """Update the current cognition step number."""
        if not self._message:
            return
        self._step_count = step
        # Don't flush for step updates alone — they'll be included in next tool update

    async def update_agents(self, agent_states: dict[str, tuple[str, str]]):
        """
        Update agent swarm status.

        Args:
            agent_states: {agent_id: (topic, status_emoji)} e.g.
                          {"agent-a1b2": ("Quantum Consciousness", "✅")}
        """
        if not self._message:
            return
        self._agent_states = agent_states
        self._pending_update = True
        await self._flush()

    async def finalize(self):
        """Edit the status embed into a completed state — preserves history."""
        if not self._message:
            return
        # Cancel any pending deferred flush
        if self._deferred_task and not self._deferred_task.done():
            self._deferred_task.cancel()
        try:
            elapsed = time.time() - self._start_time if self._start_time else 0
            elapsed_str = f"{elapsed:.0f}s" if elapsed < 60 else f"{elapsed/60:.1f}m"

            lines = []

            # ── Header ──
            if self._agent_states:
                total = len(self._agent_states)
                done = sum(1 for _, (_, s) in self._agent_states.items() if s in ("✅", "🏆", "❌"))
                failed = sum(1 for _, (_, s) in self._agent_states.items() if s == "❌")
                header = f"✅ Complete — {done} agent(s), {self._tool_count} tools, {elapsed_str}"
                if failed:
                    header += f" ({failed} failed)"
                lines.append(header)
            elif self._tool_count > 0:
                lines.append(f"✅ Complete — {self._tool_count} tools used in {self._step_count} steps ({elapsed_str})")
            else:
                lines.append(f"✅ Complete ({elapsed_str})")

            # ── Tool chain (all tools, up to 8) ──
            if self._status_lines:
                shown = self._status_lines[-8:]
                if len(self._status_lines) > 8:
                    lines.append(f"│ ... {len(self._status_lines) - 8} earlier tools")
                for line in shown:
                    lines.append(f"│ ✓ {line}")

            # ── Agent final states ──
            if self._agent_states:
                lines.append("│")
                total = len(self._agent_states)
                if total > 15:
                    # Collapsed view for large swarms
                    done = sum(1 for _, (_, s) in self._agent_states.items() if s == "✅")
                    failed = sum(1 for _, (_, s) in self._agent_states.items() if s == "❌")
                    won = sum(1 for _, (_, s) in self._agent_states.items() if s == "🏆")
                    parts = [f"✅ {done + won} completed"]
                    if failed:
                        parts.append(f"❌ {failed} failed")
                    lines.append(f"├─ {total} agents: {' · '.join(parts)}")
                    # Show last 5 completed agents
                    completed = [(aid, t) for aid, (t, s) in self._agent_states.items() if s in ("✅", "🏆")]
                    if completed:
                        for aid, topic in completed[-5:]:
                            clean = topic.split(' — ')[0] if ' — ' in topic else topic
                            lines.append(f"│  ✅ {clean[:60]}")
                        if len(completed) > 5:
                            lines.append(f"│  ... and {len(completed) - 5} more")
                else:
                    for aid, (topic, status) in self._agent_states.items():
                        clean_topic = topic.split(' — ')[0] if ' — ' in topic else topic
                        lines.append(f"├─ {status} {clean_topic}")

            content = "\n".join(lines)
            if len(content) > 3900:
                content = content[:3900] + "\n... (trimmed)"

            import discord
            embed = discord.Embed(
                description=f"```\n{content}\n```",
                color=0x57F287,  # Green for completed
            )
            await self._message.edit(embed=embed)
        except Exception as e:
            logger.debug(f"CognitionTracker.finalize failed (non-fatal): {e}")
        finally:
            self._message = None

    async def _flush(self):
        """Debounced embed edit — max 1 edit per EDIT_DEBOUNCE seconds."""
        if not self._message or not self._pending_update:
            return

        now = time.time()
        if now - self._last_edit < self.EDIT_DEBOUNCE:
            # Schedule a deferred flush if none is pending
            if not self._deferred_task or self._deferred_task.done():
                self._deferred_task = asyncio.create_task(self._deferred_flush())
            return

        await self._do_edit()

    async def _deferred_flush(self):
        """Wait for debounce window then flush."""
        remaining = self.EDIT_DEBOUNCE - (time.time() - self._last_edit)
        if remaining > 0:
            await asyncio.sleep(remaining)
        if self._pending_update:
            await self._do_edit()

    async def _do_edit(self):
        """Actually edit the Discord message."""
        async with self._update_lock:
            if not self._message or not self._pending_update:
                return

            self._pending_update = False
            self._last_edit = time.time()

            elapsed = time.time() - self._start_time if self._start_time else 0
            elapsed_str = f"{elapsed:.0f}s" if elapsed < 60 else f"{elapsed/60:.1f}m"

            lines = []

            # ── Header with elapsed time ──
            if self._agent_states:
                total = len(self._agent_states)
                done = sum(1 for _, (_, s) in self._agent_states.items() if s in ("✅", "🏆", "❌"))
                running = total - done
                if running > 0:
                    lines.append(f"🧠 Swarm [{done}/{total}] — {running} working ({elapsed_str})")
                else:
                    lines.append(f"🧠 Swarm [{done}/{total}] — Complete ({elapsed_str})")
            elif self._tool_count > 0:
                lines.append(f"⚡ Step {self._step_count} — {self._tool_count} tools ({elapsed_str})")
            else:
                lines.append(f"⏳ Thinking... ({elapsed_str})")

            # ── Completed tools (last 4, compact) ──
            if self._status_lines:
                if len(self._status_lines) > 4:
                    hidden = len(self._status_lines) - 4
                    lines.append(f"│ ... {hidden} earlier tools")
                recent = self._status_lines[-4:]
                for line in recent:
                    lines.append(f"│ ✓ {line}")

            # ── Agent states: collapsed for large swarms ──
            if self._agent_states:
                lines.append("│")
                total = len(self._agent_states)
                if total > 15:
                    # Summary bar for large swarms
                    done = sum(1 for _, (_, s) in self._agent_states.items() if s in ("✅", "🏆"))
                    failed = sum(1 for _, (_, s) in self._agent_states.items() if s == "❌")
                    running = total - done - failed
                    bar_parts = []
                    if done:
                        bar_parts.append(f"✅ {done}")
                    if running:
                        bar_parts.append(f"🔄 {running}")
                    if failed:
                        bar_parts.append(f"❌ {failed}")
                    lines.append(f"├─ {total} agents: {' · '.join(bar_parts)}")
                    # Show 3 currently active agents
                    active = [(aid, t) for aid, (t, s) in self._agent_states.items() if s not in ("✅", "🏆", "❌")]
                    for aid, topic in active[:3]:
                        lines.append(f"│  🔄 {topic[:60]}")
                    if len(active) > 3:
                        lines.append(f"│  ... +{len(active) - 3} more working")
                else:
                    for aid, (topic, status) in self._agent_states.items():
                        lines.append(f"├─ {status} {topic}")

            # ── Current action (what's running RIGHT NOW) ──
            if self._current_action:
                lines.append(f"└─ {self._current_action}")
            elif not self._agent_states:
                lines.append("└─ 🧠 Reasoning...")

            content = "\n".join(lines)

            # Discord embed limit is 4096 chars — trim if needed
            if len(content) > 3900:
                content = content[:3900] + "\n... (trimmed)"

            try:
                import discord
                embed = discord.Embed(
                    description=f"```\n{content}\n```",
                    color=0x5865F2,
                )
                await self._message.edit(embed=embed)
            except Exception as e:
                logger.debug(f"CognitionTracker edit failed (non-fatal): {e}")
