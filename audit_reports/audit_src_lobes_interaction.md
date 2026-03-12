# Audit Report: `src/lobes/interaction/` The Interaction Center

## Overview
The "Interaction" lobe manages Ernos's connection to the external world, facts, logic, and social relationships. It coordinates perception, empirical computation, deep research, social trust, and group dynamics.

## 1. `bridge.py` (BridgeAbility)
- **Function**: Public Memory & Cross-Pollination.
- **Key Logic**:
  - Searches for `PUBLIC` data across three layers:
    1. Public files (`memory/public/`).
    2. Vector memory marked with `PrivacyScope.PUBLIC`.
    3. Knowledge Graph nodes marked as `SYSTEM` (where `user_id = -1`).
  - Allows Ernos to tap into global system knowledge or safe shared data without breaching private silos.

## 2. `conflict_sensor.py` (ConflictSensor)
- **Function**: v3.3 Mycelium Network Tension Detection.
- **Key Logic**:
  - **Hybrid Architecture**: Uses a synchronous, regex/keyword-based "fast pre-filter" to instantly score a message (e.g., catching aggression keywords, shouting, tension markers).
  - If the raw tension score is > 0.15, it triggers an asynchronous AI refinement using the active LLM engine to check for sarcasm, gaming vernacular (e.g., "kill" in Minecraft), or cultural contexts.
  - Recommends an action for the bot: `normal`, `acknowledge`, `soften_tone`, or `de-escalate`.

## 3. `group_dynamics.py` (GroupDynamicsEngine)
- **Function**: Channel/Group Conversation Tracking.
- **Key Logic**:
  - Records who talks to whom (turn-taking pairs), dominant speakers, and "quiet users" (users speaking < 30% of average) within a channel.
  - Ernos uses this data to proactively engage quieter users and understand if it should interject or let the human conversation flow.
  
## 4. `perception.py` (PerceptionEngine)
- **Function**: Multi-modal Sensory Aggregator (Rhizome v3.4).
- **Key Logic**:
  - Buffers multi-modal inputs (`text`, `image`, `audio`, `game_state`, `sensor`).
  - Condenses recent inputs into a single `PerceptionContext` snapshot defining the bot's "attention focus" and "dominant modality."
  
## 5. `researcher.py` (ResearchAbility)
- **Function**: Autonomous Deep Research.
- **Key Logic**:
  - Delegates heavy research tasks to a full autonomous Agent via `AgentSpawner` rather than a simple search.
  - Upon completion, the ability automatically parses the research report and forces an LLM to extract 5-15 strictly formatted Knowledge Graph triples (`subject`, `predicate`, `object`).
  - Pushes these triples into the system's `OntologistAbility` for validation and permanent storage.

## 6. `science.py` (ScienceAbility)
- **Function**: Empirical Verification & Math (The Mini Lab).
- **Key Logic**:
  - Supports computational modes: `compute`, `eval`, `solve`, `stats`, `physics`, `chemistry`, and `matrix`.
  - Determines conceptually vs computationally driven queries dynamically via LLM check.
  - Implements a heavily restricted, 10-second sandboxed Python evaluation step using a subprocess for complex math (`numpy`, `scipy`, `sympy`).
  - Statically blocks system imports/builtins to prevent sandbox escape (`os`, `subprocess`, file I/O).

## 7. `social.py` (SocialAbility)
- **Function**: Relationship & Trust Manager.
- **Key Logic**:
  - Tracks user interactions to calculate a 0-100 Trust Score (`STRANGER` to `CLOSE`).
  - Trust rises via conversation volume, longevity (time since first seen), and sentiment (ratio of positive to negative interactions).
  - Listens to emoji reactions (`process_reaction`) to organically adjust the sentiment metrics.
