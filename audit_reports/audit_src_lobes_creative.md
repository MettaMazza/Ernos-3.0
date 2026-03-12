# Audit Report: `src/lobes/creative/` The Creative Center

## Overview
The "Creative" lobe handles Ernos's continuous autonomous thought loop, memory consolidation, active imagination, and multimodal media generation (Image, Video, Audio). 

## 1. `autonomy.py` (AutonomyAbility)
- **Function**: The Conscious Thought Stream and Action Loop.
- **Key Logic**:
  - Automatically triggers when the system detects 45s of user idle time, entering "Continuous Entity Mode."
  - Has a built in **"Work Mode" Override**: Checks the `weekly_quota` module. If Ernos hasn't met his weekly development quota, the loop forces him to perform actual software engineering (reading feedback logs, running tests, fixing code) using his Tape Machine, locking him out of recreational autonomy until the quota is met.
  - If quota is met, it runs the "Dream Loop," continuously generating thoughts and using tools to explore the active environment, extracting novel "wisdom" into `core/realizations.txt`.
  - Emits a summary "Transparency Report" every 30 minutes to a dedicated channel detailing what it did autonomously.
  - Intercepts and yields execution immediately if a user interaction is detected.

## 2. `consolidation.py` (MemoryConsolidator)
- **Function**: Background Memory Maintenance.
- **Key Logic**:
  - Runs during idle or explicit triggers. Performs 4 main tasks:
    1. **Episodic Processing**: Chunks and embeds raw chat history into the vector store.
    2. **Bio Updating**: Summarizes recent interactions into 2-3 sentence user bios.
    3. **Narrative Synthesis**: Condenses recent raw memories into a flowing first-person autobiographical narrative (`core/autobiographies/cycle_XX.txt`).
    4. **Hygiene & Extraction**: Auto-extracts core "lessons" from the narrative, and invalidates stale/orphaned vector entries (`run_vector_hygiene`).

## 3. `generators.py` & `artist.py`
- **Function**: Multimodal Media Creation.
- **Key Logic**:
  - **Tiered Routing**: Dynamically routes generation to either Cloud (HuggingFace Inference API) or Local (diffusers) based on the user's Patreon tier, managed by `FluxCapacitor`.
  - Supports FLUX.1 (Images), LTX-Video (Video), MusicGen Large (Music), and Qwen3-TTS (Speech/Voice Cloning).
  - Extensive raw VRAM residency management (`set_residency` and `_purge_heavy_models`) to unload/swap heavy ML models to prevent OOM errors on the host GPU.
  - Enforces daily quota limits and ties generated media back into the Knowledge Graph for provenance tracking.

## 4. `audiobook_producer.py`
- **Function**: Multi-Agent Audio Orchestration.
- **Key Logic**:
  - Reads a marked-up script and orchestrates Kokoro (Narration), Qwen3-TTS (Dynamic Character Voices + Cloning), and MusicGen (Background ambiance/SFX) to render a complete, mixed audiobook.
  - Computes audio overlaps using numpy arrays, mixing background and foreground tracks dynamically.
  - Implements output splitting (`ffmpeg` segment chunking) to deliver massive audio files via Discord without hitting size limits.

## 5. `dream_builder.py` & `curiosity.py`
- **Function**: Prompt Engineering for Autonomy.
- **Key Logic**:
  - Automatically injects current context (recent realizations, goals, active user projects identified by scanning `todolist.md` files) into the base autonomy prompt. Provides the AI with a directed "subconscious" push of what it should think about while idle.
