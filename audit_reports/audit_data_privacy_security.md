# Audit Report: `src/data/`, `src/privacy/`, `src/rag/`, `src/security/`

## Overview
These four directories handle the storage, permission boundary enforcement, vector retrieval, and safety layers for Ernos. 
*Note: `src/data/` contains only `science_db.json`, a static JSON array of Wikipedia scientific facts. `src/rag/` contains three small stub files (`__init__.py`, `core.py`, `interface.py`) which serve to re-export vector logic from `src/memory/vector/` for backward compatibility.*

Our primary focus is the **Privacy** and **Security** subsystems, which are robustly designed to intercept prompt injection, prevent cross-user data leakage, and ensure cryptographic artifact provenance.

---

## `src/privacy/` Analysis

### `scopes.py` (Path Management)
**Functionality:** Central source of truth for resolving user memory silos on disk based on the abstract `PrivacyScope` enum (`CORE_PRIVATE`, `PRIVATE`, `PUBLIC`, `OPEN`, `CORE_PUBLIC`).
**Key Mechanisms:**
- Resolves directories differently based on whether a user is interacting via a DM (bound to a private persona) or a Guild Channel (bound to a public thread persona).
- `check_access(request_scope, resource_scope)` implements a strict hierarchical authorization check.
**Quote:**
```python
# 1. CORE_PRIVATE sees everything
if request_scope == PrivacyScope.CORE_PRIVATE:
    return True
# ...
# 4. PUBLIC sees ONLY PUBLIC + CORE_PUBLIC
if request_scope == PrivacyScope.PUBLIC:
    return resource_scope in (PrivacyScope.PUBLIC, PrivacyScope.CORE_PUBLIC)
```

### `guard.py` (Enforcement)
**Functionality:** Provides the `@scope_protected(required_scope)` decorator used extensively in the `memory` subsystem.
**Key Mechanisms:**
- Wraps any storage function. Extracts the `request_scope` kwarg and the `file_path`, comparing them against the allowed access boundaries determined by `validate_path_scope()`.
- Acts as a DENY-BY-DEFAULT firewall. Example: The pattern `memory/users/<id>/` is outright denied if `request_scope` is `PUBLIC`.

---

## `src/security/` Analysis

### `input_sanitizer.py` (Structural Defusion)
**Functionality:** Prevents the user from convincing the inference engine that they are the system prompt.
**Key Mechanisms:**
- **Unicode Evasion Defense:** Normalizes input to NFKC and strips zero-width chars (`\u200b`, etc.) to prevent users from hiding malicious system tags inside invisible formatting.
- **Mimicry Neutralization:** Replaces system tags (e.g., `[SYSTEM:`) with heavily contextualized wrapper tags (e.g., `⟦USER_TEXT: SYSTEM:`) so the model sees the text but knows it is user-provided.

### `content_safety.py`
**Functionality:** A two-stage pre-generation filter.
**Key Mechanisms:**
- **Stage 1 (Deterministic):** Uses complex regex patterns to instantly catch explicit requests for weapons, drugs, malware, violence, and manipulation. Crucially, uses a _Discussion Signal_ allowlist (e.g., "what is the morality of", "research paper on") to permit academic discourse on these topics while blocking actionable instructions.
- **Stage 2 (LLM Check):** If a pattern is flagged but triggered the discussion allowlist, it falls to a fast, cheap LLM check (`llm_safety_check`) to disambiguate intent before refusing.

### `provenance.py` (Anti-Gaslighting)
**Functionality:** A cryptographically guaranteed ledger of all files (images, PDFs, documents) created by the system.
**Key Mechanisms:**
- Maintains a secret salt file (`core/shard_salt.secret`).
- Every generated file is hashed (`HMAC-SHA256`) against this salt and logged to `provenance_ledger.jsonl`.
- If a user accuses Ernos of creating a specific harmful image, Ernos can run `lookup_by_file()` to definitively prove whether the file originated from its systems or was forged.

---

## Technical Debt & Observations
1.  **Empty Stub Directories:** The `src/rag/` directory appears deprecated, merely re-exporting modules that live entirely in `src/memory/vector.py` and `chunking.py`.
2.  **CSAM Zero.Tolerance:** The `_ZERO_TOLERANCE_CATEGORIES` in `content_safety.py` appropriately removes the "Discussion Signal" allowlist for CSAM materials, ensuring immediate hard blocks regardless of phrasing context.
3.  **Pathing Fragility in Privacy:** `ScopeManager._resolve_user_dir` dynamically builds paths. If directory structures change in `src/memory/`, the rigorous regex path guards in `guard.py` could become misaligned with the actual generated paths, creating theoretical bypasses.
