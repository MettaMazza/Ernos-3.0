# Audit Report: `src/memory/` Learning, Validation & Reconciliation

## Overview
This report covers Tier 4 & 5 memory subsystems (Timeline and Lessons), as well as the advanced validation and cross-tier reconciliation engines.

## 1. `reconciler.py`
- **Function**: The `CrossTierReconciler` detects disagreements between memory tiers.
- **Key Logic**:
  - Runs synchronously inside `Hippocampus.recall()`.
  - Takes retrieved `KG Facts` and `Vector Memories` and submits them to the active LLM engine with the `RECONCILIATION_PROMPT`.
  - Instructs the LLM to identify instances where the semantic vector memory is outdated or directly contradicts the highly-structured KG fact.
  - Automatically prepends `[⚠️STALE?]` to the vector memory text before it reaches the core prompt, signaling to the primary cognitive process that this piece of context may be a hallucination or superseded truth.

## 2. `validators.py`
- **Function**: `ValidatorFactory` and its 26 `LayerValidator` implementations.
- **Key Logic**:
  - Enforces "Neuro-Symbolic" constraints on the Knowledge Graph. Examples:
    - `CausalValidator`: Rejects relationships where a node causes itself.
    - `TemporalValidator`: Rejects `CAUSES` relationships where the target timestamp precedes the source timestamp.
    - `SocialValidator`: Rejects any node or relation lacking a `user_id`, guaranteeing privacy tracking for social data.
    - `SymbolicValidator`: Blocks tautologies (e.g., A `IS_LIKE` A).
    - `CoreProtectionValidator`: Prevents any process (except the Mediator Agent or Foundation Seed) from mutating `user_id=-1` core data.

## 3. `lessons.py` & `timeline.py`
- **Function**: Tier 5 (Lessons) and Tier 4 (Timeline).
- **Key Logic**:
  - `LessonManager`: Stores user-specific explicit directives (`"verification_status" = "verified"`) with confidence scores and cryptographic provenance hashes.
  - `Timeline`: An append-only chronological event log. Writes are strictly scoped; `PRIVATE` events are only written to the user's secure silo directory and skipped in the global timeline.

## 4. `salience.py`
- **Function**: Defines the `SemanticSalienceEngine`.
- **Key Logic**:
  - Evaluates every incoming message using an LLM prompt (`_score_via_llm`) to assign an importance score (0.0 to 1.0) based on emotional disclosure, factual content, or project instructions, filtering out low-salience chit-chat from triggering expensive memory consolidation processes.
