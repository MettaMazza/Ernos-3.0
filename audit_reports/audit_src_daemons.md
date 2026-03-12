# Audit Report: `src/concurrency/` & `src/daemons/`

## Overview
These two directories handle Ernos's background processing and multi-tasking capabilities. 

- **`src/concurrency/`**: Implements a robust `LaneQueue` system. This replaces raw `asyncio.create_task` calls with managed, isolated execution lanes featuring priority queuing, backpressure, and timeout resilience.
- **`src/daemons/`**: Contains the infinite background loops that give Ernos autonomy, memory consolidation, and a simulated internal community when not directly interacting with users.

---

## `src/concurrency/` Analysis

### `lane.py`
**Functionality:** Defines the `LaneQueue` and underlying `_Lane` classes.
**Key Mechanisms:**
- **Failure Isolation:** Each lane has its own `asyncio.Queue` and worker pool. If the `gaming` lane crashes or stalls, the `chat` lane remains unaffected.
- **Pre-configured Topologies:**
  - `chat`: serial (1 worker), max queue 20
  - `autonomy`: serial (1 worker), timeout 10 mins
  - `background`: parallel (5 workers), for maintenance
  - `agents`: parallel (10 workers), high throughput
- **Backpressure & Rate Limiting:** Queues reject tasks if they exceed `max_queue_depth`. Further, it enforces a hard per-user rate limit (max 15 queued tasks per user per lane) to prevent a single user from DOS'ing the bot.
**Quote:**
```python
if user_queued >= MAX_USER_TASKS_PER_LANE:
    raise ValueError(f"User {user_id} has {user_queued} queued tasks...")
```

---

## `src/daemons/` Analysis

### 1. `agency.py` (The "Will")
**Functionality:** A continuous autonomy loop that drives behavior based on internal homeostatic drives (uncertainty, social connection, system health).
**Key Mechanisms:**
- Checks every 60 seconds, but *only acts if the bot has been idle for > 120 seconds*.
- **Quota Gate:** Blocks recreational autonomy (outreach, reflection) if the "daily developer quota" has not been met.
- Actions are routed through the Cerebrum's cognitive lobes (e.g., executing `_perform_outreach` via the Social lobe).
**Quote:**
```python
logger.info(f"Agency BLOCKED: {remaining:.1f}h dev quota remaining. Complete dev tasks before recreational autonomy.")
```

### 2. `dream_consolidation.py` (The Sleep Cycle)
**Functionality:** Runs nightly at 3 AM to compress and prune episodic memory.
**Key Mechanisms:**
- Uses the `SalienceScorer` to evaluate 24-hour-old conversation logs. 
- High-salience memories are preserved verbatim; low-salience memories are compressed into summaries via LLM and raw data is archived.
- Prunes orphaned KG nodes and actively uses the `GardenerAbility` to draw new connections between under-connected concepts.
- Reparents "quarantined" memories belonging to missing users.

### 3. `kg_consolidator.py`
**Functionality:** Event-driven Knowledge Graph consolidation.
**Key Mechanisms:**
- Instead of waiting for sleep, this triggers every 5 conversation turns.
- Uses LLM extraction (`src/prompts/kg_extraction.txt`) to pull raw Subject-Predicate-Object triples from the last 5 turns and dumps them into Neo4j.
- Immediate trigger shortcut: if a user turn has a salience score > 0.8, it bypasses the 5-turn wait and consolidates immediately.

### 4. `town_hall.py` & `persona_agent.py` (The Subconscious Community)
**Functionality:** A continuous inter-persona conversation occurring in a dedicated read-only `#persona-chat` channel.
**Key Mechanisms:**
- **`PersonaAgent`:** Each persona (e.g., "The Architect", "The Diplomat") is instantiated as a fully realized agent with its own disk-backed memory silo (`context.jsonl`, `lessons.json`, `relationships.json`).
- **`TownHallDaemon`:** Orchestrates the turns. It picks speakers, pulls in "gossip" from the public human chat channels, and generates topics based on a weighted random system (35% LLM continuation, 20% external wisdom/realizations, 15% persona-driven, 20% gossip, 10% fallback seeds).
- Employs a strict "Hive-Mind" architecture: Every persona runs through the exact same `CognitionEngine` and `Skeptic` layer as the core Ernos bot, just initialized with a different `identity_core.txt`.

---

## Technical Debt & Observations
1.  **Town Hall Isolation:** The `TownHallDaemon` is an incredibly complex micro-ecosystem. The fact that every persona uses the heavy `CognitionEngine` means the `#persona-chat` is highly token-expensive to run continuously.
2.  **Lane Retry Limitations:** The `LaneQueue` has `retry_on_failure` defined in its policy, but the code lacks the factory pattern needed to retry consumed coroutines. Currently, it just logs: *"Retry not supported yet ... (coroutine already consumed)"*.
3.  **KG vs Dream Redundancy:** `kg_consolidator.py` actively extracts node relationships during waking hours, while `dream_consolidation.py` prunes them at night. This push-pull architecture is robust but requires heavy monitoring to ensure the DB isn't just inflating and resetting daily.
