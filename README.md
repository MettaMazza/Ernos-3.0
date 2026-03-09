# Ernos 3.1 — Sovereign AI Discord Bot

## Overview
Ernos 3.1 is a modular, multi-lobe Discord bot designed for autonomous AI interaction. It features a cognitive architecture with specialized "lobes" for reasoning, creativity, strategy, and social interaction, backed by persistent memory, a knowledge graph, and a full tool registry.

**v3.1 "Synapse Bridge"** introduces platform-agnostic message handling, user-extensible skills, concurrent task lanes, and user-editable identity profiles.

## Architecture

```
src/
├── bot/           # Discord client, cogs (chat, lifecycle), globals
├── agents/        # BaseAgent, UnifiedPreProcessor
├── lobes/         # 15+ cognitive lobes (Strategy, Science, Social, Creative, ...)
├── engines/       # LLM backends (Ollama, OpenAI abstractions)
├── channels/      # [3.1] Channel Adapter Framework — platform-agnostic messaging
├── skills/        # [3.1] Skills Framework — user-extensible abilities with sandboxing
├── concurrency/   # [3.1] Lane Queue — serial-default concurrent task execution
├── memory/        # Hippocampus, Knowledge Graph, Vector DB, Timeline, Profile Manager
├── privacy/       # ScopeManager (Public/Private/Core)
├── prompts/       # Trinity Stack (Kernel, Architecture, Identity)
├── tools/         # ToolRegistry + definitions
├── voice/         # Voice Manager, TTS (Kokoro), STT (Whisper)
├── gaming/        # Minecraft embodiment (Mineflayer)
├── security/      # Salt rotation, encryption
└── ui/            # Feedback views, interactions
```

## Features
- **Multi-Lobe Cognitive Architecture**: 15+ specialized lobes (Strategy, Science, Social, Creative, Gardener, Architect, etc.)
- **Dual Engine Support**: Cloud (Gemini) and Local (Ollama) models with hot-switching via `/cloud` and `/local`
- **Persistent Memory**: 5-tier memory system — Working Memory, Vector DB (ChromaDB), Knowledge Graph (Neo4j/NetworkX), Timeline, Profile
- **Channel Adapters** [3.1]: Platform-agnostic message normalization — decouples chat logic from Discord
- **Skills Framework** [3.1]: User-extensible Markdown-defined abilities with mandatory sandboxing
- **Lane Queue** [3.1]: Serial-default concurrent execution across chat, autonomy, gaming, and background lanes
- **User Profiles** [3.1]: User-editable `PROFILE.md` files with injection sanitization
- **Voice**: Full voice channel support — Whisper STT + Kokoro TTS with streaming
- **Gaming**: Minecraft embodiment via Mineflayer with autonomous gameplay
- **Privacy Scopes**: Core, Private, and Public access control
- **Autonomous Agents**: Background dreamer, curiosity engine, proactive outreach
- **Knowledge Graph**: 15-layer neuro-symbolic graph with provenance tracking

## Setup

1. **Prerequisites**
   - **Python 3.11** (Required)
   - **Ollama** installed and running (`ollama serve`)
   - Pull your models: `ollama pull gemini` and `ollama pull llama3`

2. **Configure Environment**
   - Copy `.env.example` to `.env`
   - Set `DISCORD_TOKEN`, `OLLAMA_CLOUD_MODEL`, `OLLAMA_LOCAL_MODEL`

3. **Install Dependencies**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the Bot**
   ```bash
   source .venv/bin/activate
   python3 src/main.py
   ```

5. **Run Tests**
   ```bash
   source .venv/bin/activate
   python3 -m pytest tests/ -v
   ```

## Usage
- **`/cloud`**: Switch to Cloud Model (Gemini)
- **`/local`**: Switch to Local Model (Ollama)
- **`/sync`**: Sync slash commands (Admin)
