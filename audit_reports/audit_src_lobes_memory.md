# Audit Report: `src/lobes/memory/` The Memory Center

## Overview
The "Memory" lobe manages the interface between the agent's cognition and the underlying `Hippocampus` storage layer (Vector DB + Knowledge Graph). It governs scope security during retrieval, validates and scores new facts before ingestion, and curates long-term narrative journals.

## 1. `curator.py` (CuratorAbility)
- **Function**: Scope-Secured Vector Retrieval.
- **Key Logic**:
  - Enforces `PUBLIC` / `PRIVATE` Scope Gates.
  - Queries `Hippocampus.recall` but adds a crucial secondary post-retrieval validation step. Even if `Hippocampus` returns a result, the `Curator` drops it if the request scope is `PUBLIC` but the item string contains `[PRIVATE]`.
  - Binds the validated snippet to the current `working` memory transcript as a `"system"` message.

## 2. `journalist.py` (JournalistAbility)
- **Function**: Narrative Timeline Generation.
- **Key Logic**:
  - Fetches recent events from `hippocampus.timeline` (filtered by the user's `PrivacyScope`).
  - Appends bulleted narratives to markdown files: `data/system/core/journal.md` (for `CORE` scope) or `data/system/public/journal.md` (for `PUBLIC` scope).

## 3. `librarian.py` (LibrarianAbility)
- **Function**: Large Document Reader.
- **Key Logic**:
  - Reads text/code files locally. Uses a cursor dictionary `{file_hash: current_line}` to paginate files in chunks (default 50 lines) to prevent LLM context overflow.
  - Provides a `analyze_file_density` function to estimate token counts.

## 4. `ontologist.py` (OntologistAbility)
- **Function**: Foundation-Aware Knowledge Graph Ingestion.
- **Key Logic**:
  - **Question Filtration**: Uses a heuristic (`"how", "what", "if", "can"`, etc. combined with `?`) and a secondary LLM check to reject user questions meant for `search_web` instead of fact ingestion.
  - **Foundation Validation Check**: Checks if the claim contradicts established `CORE` knowledge. If a contradiction is detected, it always routes the claim to `MediatorAbility` (Superego Lobe) to `ACCEPT`, `REJECT`, `ANNOTATE`, or `DEFER`.
  - **Confidence Scoring (0.0 to 1.0)**:
    - Base: 0.15
    - Trusted Admin/Bot Source: +0.15
    - Foundation Alignment: +0.15 to +0.25
    - Source Provided (URL): +0.20 (Bonus +0.05 for `.edu`, `.gov`, `nature.com`, etc.)
    - Plausibility (Valid relationship verbs): +0.20
    - Historical User Accuracy: Scans Neo4j for how many facts this `user_id` has previously contributed. >50 facts = +0.2, >10 = +0.15.
    - Verifiability (e.g. `CAPITAL_IS` vs `THINKS`): +0.10
  - **Thresholds**: Evaluates the final score. `>= 0.5` stores directly. `>= 0.25` sends to `quarantine` for review. `< 0.25` pushes back to the user asking for sources.

## 5. `recall.py` (RecallAbility)
- **Function**: Direct Search Specialist.
- **Key Logic**:
  - A thin wrapper connecting the Lobe to `self.hippocampus.recall`.

## 6. `sleep.py` (SleepAbility)
- **Function**: Memory Consolidation & Dreaming.
- **Key Logic**:
  - `consolidation`: Summarizes the daily working memory context into key facts via LLM.
  - `dream`: Stubbed out. Intended to run "What if?" LLM simulations on recent historical events.
