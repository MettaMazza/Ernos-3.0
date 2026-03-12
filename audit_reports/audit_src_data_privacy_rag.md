# Audit Report: `src/data/`, `src/privacy/`, and `src/rag/` Subsystems

## Overview
This report groups three smaller but highly critical subsystems: local datasets (`data`), scope and path security enforcement (`privacy`), and text embeddings base classes (`rag`).

## Part 1: `src/data/`
### 1. `science_db.json`
- **Function**: A lightweight, hardcoded JSON database of physical and chemical constants. Used by the `ScienceLobe`.
- **Key Logic**: Provides real-time, zero-latency grounding without requiring a web search or Vector DB lookup. Contains the periodic table elements and foundational constants ($c, G, h, m_e, N_A$, etc.).

## Part 2: `src/privacy/`
This subsystem is arguably one of the most important security mechanisms in the entire bot, strictly segmenting memory silos and preventing cross-user contamination or context leaking.

### 1. `scopes.py`
- **Function**: Defines `PrivacyScope` Enums and resolves filesystem boundaries via `ScopeManager`.
- **Key Logic**:
  - DMs map to `PRIVATE` scope. Guild (server) channels map to `PUBLIC` scope. The internal system processes as `CORE_PRIVATE`.
  - Determines if a request from one scope can read data generated from another. For instance, `PUBLIC` can only view `PUBLIC` and `CORE_PUBLIC` data. `PRIVATE` can view `PRIVATE`, `PUBLIC`, and `CORE_PUBLIC` data.
- **Quote**:
  ```python
          # 2. CORE_PUBLIC sees shared world + public
          if request_scope == PrivacyScope.CORE_PUBLIC:
              return resource_scope in (PrivacyScope.CORE_PUBLIC, PrivacyScope.PUBLIC)
  ```

### 2. `guard.py`
- **Function**: Hardened path traversal protection and directory access restrictions.
- **Key Logic**:
  - `validate_path_scope` implements a mandatory **deny-by-default** firewall against all operations targeting the `memory/` directory tree.
  - Normalizes paths, decodes URL strings, strips null bytes, and prevents `../` breakouts before checking access.
  - Cross-User Access Blocks: Extracts regex match `r'memory/users/(\d+)'` to explicitly decline requests if `user_id` A tries to read `user_id` B's files, unless the invoking context is `CORE`.
- **Quote**:
  ```python
      # ── TRAVERSAL ESCAPE DETECTION ──────────────────────────────────────
      # If original path referenced memory/ but normpath resolved outside it,
      # this is a breakout attack (e.g. memory/public/../../backups/master.json → backups/master.json)
      original_references_memory = "memory/" in original_lower or original_lower.startswith("memory")
      normalized_references_memory = "memory/" in path_lower or path_lower.startswith("memory")
      if original_references_memory and not normalized_references_memory:
          logger.warning(
              f"TRAVERSAL ESCAPE BLOCKED: path '{path}' normalized to '{normalized}' "
  ```

## Part 3: `src/rag/`
This subsystem is primarily deprecated logic serving backwards compatibility, as active vector storage has been migrated directly into `src/memory/vector.py`.

### 1. `core.py` & `interface.py`
- **Function**: Defines the `BaseEmbedder` and `BaseVectorStore` abstract base classes.
- **Key Logic**: `core.py` acts exclusively as a re-export module (`from src.memory.vector import ...; __all__ = [...]`) so legacy references to `src.rag` don't break.
