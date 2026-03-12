# Audit Report: `src/memory/` Psychology & Metrics

## Overview
This report details the psychological modeling, internal state tracking, and feedback collection mechanisms within Ernos's memory subsystem.

## 1. `discomfort.py` & `emotional.py`
- **Function**: Internal State Gauges.
- **Key Logic (`discomfort.py`)**:
  - `DiscomfortMeter`: Tracks system integrity per user on a 0-100 scale.
  - Failures (e.g., `quote_fabrication`, `context_silo_failure`) add immediate points (+15 to +25) to discomfort.
  - Discomfort decays slowly at 1 point per hour of clean operation.
  - A score ≥ 85 (`FAILING`) acts as a terminal threshold that can trigger an automatic purge of the session.
  - Discomfort feeds directly into the emotional model (lowers Pleasure, spikes Arousal, lowers Dominance).
- **Key Logic (`emotional.py`)**:
  - `EmotionalTracker`: Implements the PAD (Pleasure-Arousal-Dominance) psychological model.
  - Maps natural language emotions (e.g., "frustrated", "joyful") to specific 3D coordinate targets.
  - Uses weighted averages to smoothly transition between emotional states over time.
  - Generates a visual HUD representing the current PAD state for ingestion into the core prompt.

## 2. `autobiography.py` & `chronos.py`
- **Function**: Self-Narrative & Temporal Anchoring.
- **Key Logic (`autobiography.py`)**:
  - Maintains a first-person markdown diary (`memory/core/autobiography.md`).
  - When the active file exceeds 100KB, it automatically archives the document and uses an LLM call to synthesize a comprehensive summary. This summary is injected into the top of the new file as a "continuity bridge," ensuring Ernos retains abstract context of his past without blowing up the context window.
- **Key Logic (`chronos.py`)**:
  - Manages the "Time-Chain" in the Knowledge Graph. Maps discrete Autobiography cycles to massive historical epochs (`Era: Genesis`, `Era: Continuity`) via `BELONGS_TO` relationships.

## 3. `feedback.py`
- **Function**: RLHF Data Collection.
- **Key Logic**:
  - Logs user feedback (positive/negative sentiment) with context and raw AI response text to `rlhf_feedback.jsonl`.
  - Supports exporting collected feedback to JSONL, CSV, and crucially, an Alpaca format intended for fine-tuning future iterations of the model.

## 4. `calendar.py`
- **Function**: Temporal Event Management.
- **Key Logic**:
  - Maintains scope-segregated calendar files (`CORE_PRIVATE`, `PRIVATE`, `PUBLIC`).
  - Implements custom read-visibility logic where a given scope context aggregates its own unique calendar file plus any global/public calendar files it is authorized to see.
