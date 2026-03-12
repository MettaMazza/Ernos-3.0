# Audit Report: `src/lobes/superego/` Unified Guardian System

## Overview
The "Superego" lobe contains the abilities responsible for System Integrity, Alignment, Verification, and Auditing. It serves as Ernos's internal affairs division and immune system.

## 1. `audit.py` (AuditAbility)
- **Function**: Internal Affairs / Skeptic Audit.
- **Key Logic**:
  - `audit_response()`: Uses an LLM to check if the bot is hallucinating capabilities or lying about tool execution. It injects the actual `tool_outputs`, `system_context`, and vision provenance directly into the prompt so the auditor model knows the ground truth.
  - `verify_response_integrity()`: Circuit breaker. Uses symbolic (non-LLM) stem matching to verify claims against tool history. If the bot says it "checked the code" but didn't execute `search_codebase` or `read_file`, it flags a "Symbolic Violation."

## 2. `identity.py` (IdentityAbility)
- **Function**: System Conscience / Persona Alignment.
- **Key Logic**:
  - Ensures the bot does not suffer from "Narrative Drift" or a "God Complex."
  - Specifically looks for "Architecture-as-substitute" (i.e. narrating layer numbers to avoid genuine engagement), but includes robust exceptions for Admin diagnostics, requested document generation, and provenance tracking.

## 3. `mediator.py` (MediatorAbility)
- **Function**: Knowledge Dispute Arbitrator.
- **Key Logic**:
  - Triggered during Knowledge Graph contradictions. Assesses a user's claim vs. the established CORE fact.
  - Outcomes:
    - **ACCEPT**: User is right. Updates the foundation and actively invalidates stale VDB entries via `_invalidate_stale_vectors()`.
    - **REJECT**: Foundation is right. Preserves current KG state.
    - **ANNOTATE**: Both are valid. Adds an annotation relationship.
    - **DEFER**: Sends the dispute to quarantine due to insufficient evidence.

## 4. `reality.py` (RealityAbility)
- **Function**: The Reality Guardian.
- **Key Logic**:
  - Simple verify function: Takes a user's claim, triggers a `search_web` execution, and passes the evidence through a skeptic prompt to fact-check the claim against external internet truth.

## 5. `sentinel.py` (SentinelAbility)
- **Function**: Immune System.
- **Key Logic**:
  - A semantic firewall that reviews external inputs (context shards, generated skill instructions, user profiles) against prompt injection, scope escalation, and alignment violations.
  - **Fail-Closed**: If the LLM review fails to execute, the content is automatically rejected.
  - Caches approvals by checksum to avoid re-reviewing safe/static content, persisting the cache to disk across boots.
