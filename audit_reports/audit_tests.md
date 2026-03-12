# Audit Report: `tests/`

## Overview
The `tests/` directory contains Ernos's massive automated testing suite. Comprising over 88 test files and 28 subdirectories, the suite currently registers **6,092** individual tests. 

The strategy heavily relies on `pytest` combined with extensive `unittest.mock` patching to simulate the Discord API, external LLM endpoints (Ollama, llama.cpp), and local file systems.

---

## Infrastructure Analysis

### `conftest.py` (Global Test State)
**Functionality:** Defines the universal test harness and dependency injection mocks.
**Key Mechanisms:**
- **`mock_discord_bot`:** Generates a monolithic mock of the `commands.Bot` object. It pre-attaches mock versions of the `cerebrum`, `engine_manager`, `hippocampus`, and `silo_manager`. Crucially, it overrides `bot.loop.run_in_executor` to instantly execute blocking tasks in-thread, sidestepping true async race conditions during tests.
- **`mock_ollama` & `mock_llama`:** Intercepts out-of-process engine calls, returning deterministic test responses.
- **`reset_data_dir`:** A global `autouse=True` fixture that forcibly resets the `src.core.data_paths._DATA_DIR` pointer to the local `./memory/` relative path after every test to prevent file-system state contamination between test runs.

### `test_phaseX_coverage.py` Scripts
**Functionality:** Deep structural unit tests targeting strict line-coverage thresholds.
**Key Mechanisms:**
- Scripts like `test_phase10_coverage.py` and `test_phase5_perfect_coverage.py` are built to explicitly hit obscure branch conditions, error handlers, and fallback mechanisms in the cognition lobes.
- These phase tests instantiate internal classes directly (e.g., `PerceptionEngine`, `ConflictSensor`, `SalienceScorer`) without launching the Discord bot daemon.

---

## Broad Categories of Tests

1. **Unit Tests (Core & Engines):** Files like `test_engines.py`, `test_memory_components.py`, and `test_privacy.py` rigorously validate the isolated functions of internal modules.
2. **Integration Tests (Subsystem Interactions):** Tests like `test_town_hall_hivemind.py` and `test_proactive_messaging.py` simulate cascading effects where one module (like a high tension score) must correctly trigger a response in another module (like generating a proactive DM).
3. **Regression Tests:** Files prefixed with `test_regression_` or identifying specific dates (`test_feb7_regression.py`) act as monuments to previously squashed bugs, heavily guarding against structural regressions when refactoring.
4. **Reproducer Scripts:** Standalone scripts like `reproduce_cause_tracking.py` or `verify_privacy_leak.py` appear designed as isolated runbooks to visually verify complex failure states that are hard to assert in pure pytest.

## Technical Debt & Observations
1. **Mock Monolith:** The `mock_discord_bot` fixture in `conftest.py` is over 100 lines and mocks nearly the entire application architecture. This extreme coupling means that any change to the initialization patterns in `main.py` or `chat.py` usually breaks hundreds of tests instantly.
2. **Test File Inflation:** There is heavy reliance on massive phase coverage files (ranging from 10,000 to 48,000 bytes) rather than granular `<module>_test.py` counterparts for every file. This makes finding the test for a specific function highly opaque.
