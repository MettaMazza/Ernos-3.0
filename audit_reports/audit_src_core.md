# Comprehensive Codebase Audit: `src/core/`

**Date:** 2026-02-23
**Module Path:** `src/core/`
**Purpose:** Manages Ernos's core cognitive loops, self-correction mechanisms, "metabolic" drives, rate-limiting (Flux Capacitor), and Docker security logic (Licensing & Prompt Decryption).

## Overview
The `src/core/` directory contains 6 Python files that form the beating heart of Ernos's autonomy, limitations, and security.

## File-by-File Analysis

### 1. `critical_review.py`
*   **Role:** Implements the `CriticalSelfReview` mechanism.
*   **Analysis:** When Ernos is challenged, it spawns a 3-agent internal debate: a Defender (arguing Ernos's side), a Challenger (steel-manning the user), and a Judge (evaluating both). Yields verdicts (`CONCEDE`, `HOLD`, `CLARIFY`) to avoid sycophancy or stubbornness. It uniquely updates the internal `DriveSystem` based on the outcome (e.g., conceding reduces uncertainty).
*   **Direct Quote:**
    ```python
    # From _parse_judge_output
    if parsed["verdict"] == "CONCEDE":
        # Conceding reduces uncertainty — we learned something
        drives.modify_drive("uncertainty", -10.0)
    ```

### 2. `data_paths.py`
*   **Role:** Centralizes directory resolution.
*   **Analysis:** Ensures all data writes respect the `ERNOS_DATA_DIR` environment variable, crucial for Docker volume mapping.
*   **Direct Quote:**
    ```python
    _DATA_DIR: Path = Path(os.getenv("ERNOS_DATA_DIR", "memory"))
    ```

### 3. `drives.py`
*   **Role:** Homeostatic Drive System.
*   **Analysis:** Simulates "metabolism" through three drives: `uncertainty`, `social_connection`, and `system_health`. These drives decay or increase over time (e.g., social connection decays 5% per hour of silence). This provides the signal for the `AgencyDaemon` to act autonomously. Stores state in `core/drives.json`.
*   **Direct Quote:**
    ```python
    DECAY_RATES = {
        "social_connection": 5.0,  # Loses 5% per hour of silence
        "uncertainty": -2.0        # Increases by 2% per hour naturally (entropy)
    }
    ```

### 4. `flux_capacitor.py`
*   **Role:** Manages rate limits and Patreon tier enforcement.
*   **Analysis:** Enforces limits on user messages (12-hour cycle) and specific expensive tools (daily cycle, e.g., `start_deep_research`, `generate_image`, `spawn_agent`). "Core grounding tools" remain unlimited to ensure accuracy. Provides bypasses for admins. State is persisted per-user in `users/{user_id}/flux.json`.
*   **Direct Quote:**
    ```python
    # TIER_LIMITS = { ...
    # ── GPU-EXPENSIVE (daily-based) ───────────────────────────
    "generate_image":       {"period": "daily",  0: 2,  1: 4,  2: 10, 3: 20, 4: 50},
    ```

### 5. `license.py`
*   **Role:** License key validation for Docker distribution.
*   **Analysis:** Prevents unauthorized use by checking the `ERNOS_LICENSE_KEY` environment variable against a list of valid HMAC-SHA256 hashes baked into `.license_hashes`. Refuses to boot if invalid.
*   **Direct Quote:**
    ```python
    def validate_license() -> bool:
        """
        Validate the license key from ERNOS_LICENSE_KEY env var...
        """
        key_hash = _hash_key(key)
        if key_hash in valid_hashes:
            logger.info("License key validated successfully")
    ```

### 6. `secure_loader.py`
*   **Role:** Secure asset loader.
*   **Analysis:** Decrypts AES-256-CBC encrypted prompt files (`.enc`) at runtime into memory to prevent prompt theft. Uses a baked-in secret salt and key intended to be protected by PyArmor obfuscation. 
*   **Direct Quote:**
    ```python
    # ─── Baked-in secrets (protected by PyArmor obfuscation) ───
    _SALT = b"ErnosV3-2026-AES256-Salt"
    _INTERNAL_KEY = "Ern0s-V3-2026-Int3rnal-Pr0mpt-Prot3ction-K3y-AES256"
    ```

## Conclusion
The `src/core/` directory is highly robust. It bridges the gap between simulated biology (`drives.py`), rigorous self-correction logic (`critical_review.py`), monetization enforcement (`flux_capacitor.py`), and commercial protection (`license.py`, `secure_loader.py`).

## Status 
Audited fully.
