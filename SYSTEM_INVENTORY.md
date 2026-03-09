# ERNOS 3.1 SYSTEM INVENTORY

## 1. CORE INFRASTRUCTURE
- **Bot Engine** (`src/bot`)
  - `globals.py`: Shared state (active_message, bot instance).
  - `cogs/chat.py`: Main event loop, tool parsing, Trinity injection.
  - `cogs/lifecycle.py`: Startup/Shutdown management.
  - `silo_manager.py`: Distributed consensus (Silo/Quorum) logic.
- **Entry Point** (`src/main.py`)
- **Configuration** (`config.py`, `.env`)

## 2. SYNAPSE BRIDGE (v3.1)
- **Channel Adapter Framework** (`src/channels/`)
  - `ChannelManager` (`manager.py`): Adapter registry and routing.
  - `ChannelAdapter` (`base.py`): Abstract base — normalize, send, format.
  - `DiscordChannelAdapter` (`discord_adapter.py`): Discord-specific adapter.
  - `UnifiedMessage` (`types.py`): Platform-agnostic message dataclass.
- **Skills Framework** (`src/skills/`)
  - `SkillRegistry` (`registry.py`): Skill registration, validation, manifests.
  - `SkillLoader` (`loader.py`): YAML frontmatter parser, SHA256 checksums, 10 dangerous pattern validators.
  - `SkillSandbox` (`sandbox.py`): Scope gating, tool whitelisting, rate limiting (30/hr/user).
  - `SkillDefinition` (`types.py`): Skill metadata and execution result types.
  - Default templates: `memory/core/skills/summarize_channel/`, `memory/core/skills/research_topic/`.
- **Lane Queue System** (`src/concurrency/`)
  - `LaneQueue` (`lane.py`): 4 default lanes (chat, autonomy, gaming, background).
  - `LanePolicy` / `LaneTask` (`types.py`): Configuration and lifecycle tracking.
  - Serial-default execution, backpressure, timeout, failure isolation.
- **Profile Manager** (`src/memory/profile.py`)
  - User-editable `PROFILE.md` files with injection sanitization.
  - 2000-character context limit, default template generation.

## 3. COGNITIVE ARCHITECTURE (The "Mind")
- **Agents** (`src/agents`)
  - `BaseAgent` (`base.py`): The genetic ancestor. Handles Identity/Tools.
  - `UnifiedPreProcessor` (`preprocessor.py`): The "First Thought" (Intent/Security triage).
- **Lobes** (`src/lobes`)
  - **StrategyLobe**: Executive planning, goal management.
  - **InteractionLobe**: Discord/Voice interface management.
  - **CreativeLobe**: Generative capabilities.
  - **MemoryLobe**: (Legacy) Deep storage interfaces.
  - **ScienceLobe**: STEM calculations, experiments.
  - **SocialLobe**: Community insights, group dynamics.
  - **ArchitectLobe**: Code architecture analysis.
  - **GardenerLobe**: Code structure review.
  - **JournalistLobe**: Autobiography, reflection.
  - **WorldLobe**: External research.
  - **PerformanceLobe**: Self-monitoring.
- **Engines** (`src/engines`): LLM Inference backends (Ollama/OpenAI abstractions).

## 4. MEMORY SYSTEMS (The Hippocampus)
- **Hippocampus** (`src/memory/hippocampus.py`): Central controller.
  - **Working Memory** (`working.py`): Short-term context window.
  - **Vector Database** (`vector.py`): Semantic search (ChromaDB/FAISS).
  - **Knowledge Graph** (`graph.py`): Neo4j entity/relationship storage.
  - **Timeline** (`timeline.py`): Chronological event logging.

## 5. PERCEPTION & ACTION (I/O)
- **Voice System** (`src/voice`)
  - `VoiceManager` (`manager.py`): Connection handling.
  - `AudioSynthesizer` (`synthesizer.py`): TTS (Kokoro/Espeak) with streaming.
  - `AudioTranscriber` (`transcriber.py`): STT (Whisper).
- **User Interface** (`src/ui`)
  - `ResponseFeedbackView` (`views.py`): Interactive Feedback (👍/👎/🗣️).
- **Tools** (`src/tools`)
  - `ToolRegistry` (`registry.py`): Tool registration and execution.
  - `definitions.py`: Core tool implementations.
- **Gaming** (`src/gaming`)
  - Minecraft embodiment via Mineflayer.
  - Autonomous gameplay with action chains.

## 6. GOVERNANCE & SECURITY
- **Privacy** (`src/privacy`)
  - `ScopeManager`: Access control (Public/Private/Core).
- **Security** (`src/security`)
  - Salt rotation, encryption.
- **Prompts** (`src/prompts`)
  - `PromptManager` (`manager.py`): Assembly of the Trinity Stack.
  - `kernel.txt`: Immutable laws.
  - `architecture.txt`: Self-definition.
  - `identity.txt`: Persona/Lore.
