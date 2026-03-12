# Audit Report: `ErnosClaw/` & `visualiser/`

## Overview
These two directories contain standalone client applications that interact with the core Ernos ecosystem. 
- **`ErnosClaw/`**: A native mobile application (iOS/Android) designed to connect Ernos's capabilities to Meta Ray-Ban smart glasses.
- **`visualiser/`**: A frontend web application designed to visually display the internal state, memory, and cognitive architecture of the Ernos bot in real-time.

---

## `ErnosClaw/` Analysis (VisionClaw)
**Functionality:** Acts as a bridge between the Meta Wearables DAT SDK (glasses hardware) and the Gemini Live API, bringing real-time voice and vision capabilities to the smart glasses.

**Key Mechanisms:**
- **Bidirectional Streaming:** Captures 16kHz PCM audio from the glasses' mic and `~1fps` JPEG frames from the camera, streaming them to the Gemini Live WebSocket. Returns 24kHz audio to the glasses/phone speaker.
- **OpenClaw Integration:** Bridges Gemini's function calling to a local `openclaw` gateway. When the user asks to "turn on the lights" or "send a message", Gemini generates a `toolCall`, ErnosClaw intercepts it, routes it to the local OpenClaw server (which runs 56+ scripts/tools), and returns the execution result to Gemini to speak the confirmation.
- **Cross-Platform:** Contains sub-projects for both XCode (iOS) and Android Studio, wrapping the respective native camera and audio APIs while maintaining the same WebSocket logic to Gemini.

---

## `visualiser/` Analysis
**Functionality:** A static HTML/CSS/JS web dashboard designed to provide transparency into the "Ernos Brain."

**Key Mechanisms:**
- **Telemetry UI:** Connects to Ernos's data streams to visualize complex state machines.
- **Multiple Views:**
  - **Chat:** A live web chat interface to converse with Ernos.
  - **Architecture / Pipeline:** Interactive node graphs showing how a message flows through Perception -> Sentinel -> Cerebrum.
  - **Daemons / Safety:** Real-time monitoring of the `AgencyDaemon`, `DreamConsolidationDaemon`, and the three-layer Prompt Injection/Violence filters.
  - **Memory:** A visual explorer for the Neo4j Knowledge Graph and Episodic silos.
  - **Simulator / Game:** Interactive modes to manually test prompts against specific internal filters or roleplay as the central router.

---

## Technical Debt & Observations
1. **ErnosClaw Decoupling:** ErnosClaw directly hits the `Gemini Live API` rather than routing through the `src/` core of Ernos. It uses `OpenClaw` for tools, bypassing Ernos's own `tool_registry.py`. This means interactions via the glasses do *not* populate Ernos's Hippocampus or Neo4j memory graph. 
2. **Visualiser State Sink:** The visualiser appears to be a heavy, standalone frontend. It likely relies on the `src/web/` WebSocket endpoints (audited previously) to fetch telemetry. Keeping these frontend nodes synced with rapid changes to the backend `src/lobes/` architecture will be a continuous maintenance burden.
