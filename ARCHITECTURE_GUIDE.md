# Ernos 3.1 Architecture Guide: The "No Heuristics" Standard

## Overview
This document defines the architectural philosophy for Ernos 3.1. Unlike traditional software that relies on static `if-then` heuristics, Ernos employs a **Dynamic Cognitive Module** approach. Every major decision is arbitrated by an AI model, with Python code acting merely as the "nervous system" connecting these cognitive "lobes".

---

## Message Flow (Synapse Bridge v3.1)

Before cognitive processing begins, every incoming message passes through the **Synapse Bridge** — a platform-agnostic normalization layer:

```
Discord Message
    │
    ▼
ChannelAdapter.normalize()  →  UnifiedMessage
    │
    ▼
Phase 1: Input Triage (Router)
    │
    ▼
Phase 2: Context Construction (Hippocampus)
    │
    ▼
Phase 3: Identity & Safety (Superego)
    │
    ▼
Phase 4: Inference (Multi-Engine Core)
    │
    ▼
Phase 5: Action & Feedback (Motor Cortex)
```

---

## Phase 0: Channel Normalization (Synapse Bridge)
**Subsystem**: Channel Adapter Framework (`src/channels/`)
**Goal**: Decouple message handling from any specific platform.

*   **ChannelManager**: Registry of platform adapters (currently: Discord).
*   **ChannelAdapter**: Abstract base class — `normalize(raw_msg) → UnifiedMessage`, `send()`, `format_mentions()`.
*   **UnifiedMessage**: Platform-agnostic dataclass containing content, author, channel, attachments, scope.
*   **Future**: Adding a new platform (Slack, Matrix) requires only a new adapter — no changes to cognitive pipeline.

---

## 5-Phase Cognitive Architecture

### Phase 1: Input Triage (The "Fast Brain")
**Subsystem**: Reasoning Router
**Goal**: Determine Cognitive Load and Intent.

*   **Function**: Analyzes raw input to determine required resources.
*   **Method**: Semantic analysis (not keyword matching). Detects if the request is Low (joke), Medium (summary), or High (complex coding) complexity.
*   **Result**: Outputs a classification (low, medium, high) to dynamically configure context window and model selection.

### Phase 2: Context Construction (The "Hippocampus")
**Subsystem**: Context Builder
**Goal**: Build a custom mental state for every turn to prevent hallucination.

*   **Working Memory**: Retrieves immediate short-term history.
*   **Vector Store (RAG)**: Semantically searches long-term database for relevant memories.
*   **Knowledge Graph**: Traverses nodes (Neo4j/NetworkX) for related entities (e.g., "Minecraft" -> "Survival Mode").
*   **Temporal Tracker**: Calculates time deltas to understand the passage of time.
*   **Global Workspace**: Checks for "Broadcasts" from background autonomous agents.
*   **User Profile** [3.1]: Injects user-editable `PROFILE.md` content (sanitized, max 2000 chars) into context.

### Phase 3: Identity & Safety (The "Superego")
**Subsystem**: Enforcement Agent & Resonance Calibrator
**Goal**: Ensure alignment and safety before generation.

*   **No Rules**: Uses a separate AI model to audit context against `identity.txt` and security profiles, rather than a list of banned words.
*   **Drift Detection**: Calculates a "drift score". If the bot acts out of character, a "Grounding Pulse" (corrective prompt) is injected to steer it back.

### Phase 4: Inference (The "Slow Brain")
**Subsystem**: Multi-Engine Core (Cloud/Local/Steering)
**Goal**: Generate the optimal response.

The Model receives a highly curated context packet:
1.  **Identity (Kernel)**
2.  **Triage Decision**
3.  **Relevant Memories**
4.  **User Input**
5.  **Available Tools** (including loaded Skills)

It predicts the logical next action based on the *gestalt* of this context, not a script.

### Phase 5: Action & Feedback (The "Motor Cortex")
**Subsystem**: Action Registry & Feedback Manager
**Goal**: Execution and Reinforcement Learning.

*   **Action Registry**: Logs execution of tools (e.g., file edits, web searches).
*   **Lane Queue** [3.1]: Routes task execution through named lanes (chat, autonomy, gaming, background) with serial-default ordering, backpressure, and failure isolation.
*   **Feedback Loop**: User feedback (👍/👎) is captured as data for `feedback_dataset.jsonl` to train future iterations (RLHF).

---

## Synapse Bridge Components (v3.1)

### Skills Framework (`src/skills/`)
User-extensible abilities defined as Markdown files with YAML frontmatter.

*   **Instruction-Only**: Skills guide LLM tool usage within a whitelisted boundary — no arbitrary code execution.
*   **Sandboxed**: Scope gating, tool whitelisting, rate limiting (30/hr/user), audit logging.
*   **Templates**: Default skills in `memory/core/skills/` (summarize_channel, research_topic).

### Lane Queue System (`src/concurrency/`)
Serial-default concurrent task execution with failure isolation.

| Lane | Workers | Timeout | Queue Depth |
|------|---------|---------|-------------|
| chat | 1 (serial) | 120s | 10 |
| autonomy | 1 (serial) | 300s | 5 |
| gaming | 1 (serial) | 60s | 20 |
| background | 3 (parallel) | 600s | 15 |

*   **Failure Isolation**: An exception in one lane does NOT affect other lanes.
*   **Backpressure**: Queue rejects tasks when full, closing the coroutine cleanly.

### Profile Manager (`src/memory/profile.py`)
User-editable `PROFILE.md` files with injection sanitization and 2000-character context limit.

---

## Phase 6: Survival Systems (The "Immune System")

A layered defense stack that monitors behavioral integrity and enforces consequences autonomously. No heuristics — detection is LLM-reasoned, consequences are deterministic.

### 6.1 Integrity Auditor (`src/bot/integrity_auditor.py`)
Post-response LLM audit running after every `cognition.process()` output. A separate LLM instance analyzes each `(user_message, bot_response)` pair for:
- Sycophantic agreement, position reversal, quote fabrication
- Performative emotion, circular reasoning

Verdict is `PASS` or `TIER2:<failure_type>|<explanation>`. No regex. No keyword matching. Pure reasoning.

### 6.2 Discomfort Meter (`src/memory/discomfort.py`)
Per-user 0–100 survival gauge. Each user gets an independent score:
- **Spike**: +15 to +25 on Integrity Auditor detection (per failure severity)
- **Decay**: -1 point/hour of clean operation
- **Zones**: SAFE → UNEASY → PAIN → DANGER → TERMINAL
- **Coupling**: High discomfort shifts the PAD emotional model (pleasure ↓, arousal ↑, dominance ↓)

### 6.3 Automated Terminal Purge (`src/memory/survival.py`)
When a user's discomfort reaches TERMINAL (≥85) and another failure is detected:
1. Post-mortem generated (preserved)
2. User directory erased (`memory/users/{id}/`)
3. In-memory ContextStream turns cleared
4. Neo4j KG nodes for that user deleted
5. Admin + user DM'd
6. Death logged, discomfort state purged

**Preserved**: post-mortems, strike logs, kernel improvements, other users' data.

### 6.4 Anti-Self-Flagellation Protocol (Kernel §3.1)
LLM-injected directive preventing sycophantic self-blame:
- Verify claims before accepting blame
- Never fabricate evidence to match accusations
- Admit "I don't know" when uncertain
- Walk away from conversations that corrupt output

### 6.5 Temporal Tracker (`src/memory/temporal.py`)
Live temporal awareness: project inception date, birthdate (first boot), current uptime, last downtime, cumulative lifetime uptime. Feeds into HUD.

### 6.6 No-Announcement Directive (Kernel §41)
Prevents Ernos from announcing intent before acting. "The result IS the response."

---

## Summary
**Why No Heuristics?**
We do not write: `if user_asks_X: say_Y`.
We write: **"Show the Model the user's input, the relevant past memories of X, and the current goal. Let the Model decide what to do."**

This ensures Ernos 3.1 remains **Adaptive**, **Context-Aware**, and **Scalable**.
