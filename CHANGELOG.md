# Changelog

## v3.1 "Synapse Bridge" — 2026-02-07

### Added
- **Channel Adapter Framework** (`src/channels/`) — Platform-agnostic message normalization
  - `ChannelManager` for adapter registration and routing
  - `ChannelAdapter` abstract base class
  - `DiscordChannelAdapter` for Discord-specific message handling
  - `UnifiedMessage` dataclass for platform-agnostic messaging
- **Skills Framework** (`src/skills/`) — User-extensible Markdown-defined abilities
  - `SkillRegistry` for skill registration and validation
  - `SkillLoader` with YAML frontmatter parsing and dangerous pattern detection
  - `SkillSandbox` with scope gating, tool whitelisting, rate limiting (30/hr/user)
  - Default skill templates: `summarize_channel`, `research_topic`
- **Lane Queue System** (`src/concurrency/`) — Serial-default concurrent execution
  - 4 pre-configured lanes: chat (serial), autonomy (serial), gaming (serial), background (3 parallel)
  - Per-lane backpressure, timeout, and failure isolation
  - Compatibility wrapper for existing `processing_users` API
- **Profile Manager** (`src/memory/profile.py`) — User-editable identity files
  - `PROFILE.md` loading with injection sanitization
  - 2000-character context limit
  - Default template generation
- **69 new tests** covering all Synapse Bridge components
- `CHANGELOG.md` (this file)

### Changed
- `src/bot/client.py` — Integrated `ChannelManager`, `SkillRegistry`, `SkillSandbox`, `LaneQueue` into `ErnosBot`
- `src/bot/cogs/chat.py` — Refactored `on_message` to use `adapter.normalize()` for message handling
- `tests/conftest.py` — Added `channel_manager` mock to shared `mock_discord_bot` fixture
- `ARCHITECTURE_GUIDE.md` — Rewrote with Synapse Bridge components and message flow
- `SYSTEM_INVENTORY.md` — Added Section 2 for all Synapse Bridge subsystems
- `VERIFICATION_CHECKLIST.md` — Added Sections 6-9 for new component verification
- `MASTER_SYSTEM_TEST.md` — Updated to v3.5 with Phases 16-19
- `README.md` — Full rewrite with complete feature list and architecture tree

### Fixed
- `test_autonomy_wisdom_regression.py` — Removed broken `asyncio.get_event_loop()` in setup_method
- `test_lane_queue.py` — Fixed unawaited coroutine warnings in error-path tests
- `lane.py` — Added `coro.close()` on backpressure rejection and unknown lane ValueError

## v3.0 — Initial Release
- Multi-lobe cognitive architecture
- Dual engine support (Cloud/Local)
- Persistent memory (Working, Vector, KG, Timeline)
- Voice system (Whisper STT + Kokoro TTS)
- Gaming (Minecraft embodiment)
- Privacy scopes (Core/Private/Public)
- Tool registry with 40+ tools
- Autonomous agents (Dreamer, Curiosity, Proactive)
