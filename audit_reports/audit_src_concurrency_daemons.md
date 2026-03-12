# Audit Report: `src/concurrency/` and `src/daemons/` Subsystems

## Overview
This report covers two operational subsystems responsible for task execution management and autonomous background processes in Ernos 3.0.

## Part 1: `src/concurrency/`
This module manages asynchronous execution to prevent failure cascading and provide rate-limited backpressure.

### `lane.py` & `types.py`
- **Function**: Replaces unstructured `asyncio.create_task()` calls with a structured `LaneQueue` system. Tasks are assigned to specific "Lanes" (e.g., `chat`, `autonomy`, `background`, `research`).
- **Key Logic**: 
  - Each lane runs a dedicated worker loop reading from an `asyncio.Queue`.
  - Serial-by-default (e.g., `chat` lane has `max_parallel=1`) ensuring FIFO execution without race conditions. Background tasks can be parallelized (e.g., `max_parallel=5`).
  - Strict Backpressure: Reject tasks immediately when the queue exceeds `max_queue_depth`.
  - User Rate Limiting: Users are aggressively capped to 15 concurrent queued tasks per lane.
- **Quote (`lane.py`)**:
  ```python
          # Per-user rate limiting: max 3 queued tasks per user per lane
          MAX_USER_TASKS_PER_LANE = 15
          if user_id:
              # ...
              if user_queued >= MAX_USER_TASKS_PER_LANE:
                  coro.close()
                  raise ValueError(f"User {user_id} has {user_queued} queued tasks...")
  ```

## Part 2: `src/daemons/`
This subsystem houses continuous or scheduled background operations, heavily emphasizing independent agentic behavior.

### 1. `agency.py`
- **Function**: The "Will" loop. Drives autonomous action when Ernos is idle.
- **Key Logic**: Evaluates a `DriveSystem` (uncertainty, social connection, system health). If idle for >2 minutes, asks the LLM what to do. Options: `SLEEP`, `OUTREACH` (DM check-in), `RESEARCH` (world info gathering), `REFLECTION` (internal monologue).
- *Security/Guardrails*: Adheres to a `weekly_quota` check. If the required coding/developer quotas are unmet, it blocks "recreational autonomy" (outreach/reflection).

### 2. `dream_consolidation.py`
- **Function**: The "Sleep Cycle". Triggered daily at 3:00 AM by the `TaskScheduler`.
- **Key Logic**: 
  - Episodic Memory Compression: Scans `users/` directories, uses the `SalienceScorer` to keep high-value interactions (>0.6) and archives/summarizes low-value chat logs.
  - Knowledge Graph (KG) Maintenance: Prunes old orphan nodes, attempts to infer missing relationships via `GardenerAbility`, and resolves logic errors in the "quarantine queue" using pattern matching.
  - Persists the Superego's `SentinelAbility` immune cache to disk.

### 3. `kg_consolidator.py`
- **Function**: Event-driven KG fact extractor.
- **Key Logic**: Instead of time-based triggers, this is triggered every N turns (weighted by interaction salience). It batch-processes conversational history via an LLM instruction prompt to extract `[Subject, Predicate, Object]` relationships, asserts strict `PrivacyScope` boundaries, assigns cognitive layers (e.g., narrative vs object), and pushes to Neo4j.

### 4. `town_hall.py`, `persona_agent.py`, `town_hall_generation.py`
- **Function**: Continuous inter-persona conversation sandbox (`#persona-chat`).
- **Key Logic**: 
  - Instantiates `PersonaAgent` objects (with distinct identity files, memories, lessons, and relationships).
  - Cyclically nominates a speaker and injects a generated topic based on weighted probabilities (35% LLM continuation, 20% internal insights, 15% persona suggestion, 20% public chat gossip, 10% seeds).
  - *Hive-Mind Coupling*: The generated persona response does *not* use a weak API call. It executes through the complete `bot.cognition.process()` (the main ReAct engine) overriding only the *Identity Core* file. Thus, each persona operates with Ernos's full tool suite and reasoning abilities.
- **Quote (`town_hall_generation.py`)**:
  ```python
          # SECURITY: Override identity_core_file to persona's character file
          # ...
          pm.identity_core_file = str(persona_id_file)
          # ...
          # --- Route through the FULL cognitive pipeline ---
          response = await cognition.process( # ...
  ```

## Conclusion
Both concurrency and daemon subsystems reflect massive maturation. The `LaneQueue` effectively implements the bulkhead pattern for reliability, while the daemons successfully split complex continuous state-management (Agency, Memory Consolidation, Community Simulation) across modular components capable of leveraging the base cognitive engine.
