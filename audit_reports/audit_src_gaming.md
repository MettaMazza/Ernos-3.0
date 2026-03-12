# Ernos 3.0 Audit Report: Gaming Lobe (`src/gaming/`)

This report contains the granular audit of the `src/gaming/` directory, which handles Ernos's embodiment and autonomous gameplay in Minecraft.

## Overview
The Gaming Lobe allows Ernos to connect to a Minecraft server, perceive the environment (including visual perception via screenshots), reason about its goals, and execute actions. It uses a "Predictive Chain Architecture" (combining parallel LLM thinking with precognition action chaining) to minimize bot idle time and latency.

The bridge to Minecraft is implemented via a Node.js `mineflayer` subprocess, communicating via JSON over stdin/stdout.

## Files Audited

### `__init__.py`
- **Function**: Initializes the gaming package, exposing `GamingAgent`, `MineflayerBridge`, and `get_knowledge_base`.

### `agent.py`
- **Function**: The core orchestrator for Minecraft gameplay. Extends `ActionsMixin`, `CognitionMixin`, and `PerceptionMixin`.
- **Design Decisions**:
  - Implements the main `GamingAgent` class which manages the loop: Sense -> Think -> Act.
  - Handles connecting/disconnecting to the bridge.
  - Passes commands through the `ActionsMixin`.

### `actions.py`
- **Function**: `ActionsMixin` defines high-level discrete actions for the agent.
- **Design Decisions**:
  - Supports `goto`, `collect`, `craft`, `attack`, `chat`, `follow`, `protect`, `save_location`, `scan`, `coop`.
  - Maps these to the `MineflayerBridge` method calls.

### `cognition_gaming.py`
- **Function**: `CognitionMixin` implements the "Predictive Chain" LLM architecture.
- **Design Decisions**:
  - **Fast Execution / Slow Thinking**: The engine runs in two parallel tracks. Reflexes and precognition actions are executed immediately by the bridge, while the LLM takes time to generate the next batch of actions.
  - **Failure Reflection**: Analyzes action outcomes. If an action fails, it employs heuristic analysis to understand why (e.g. missing items, unreachable block). If that fails, it queries an LLM for deeper reflection: `await self._deep_reflection(action, before_state, after_state)`.
  - **Curriculum Proposal**: When idle, proposes new goals based on the current state.

### `perception.py`
- **Function**: `PerceptionMixin` handles taking in state from the game.
- **Design Decisions**:
  - Fetches full state via `full_state` command to the bridge.
  - Captures screenshots (`get_screenshot`) with a 5s timeout fallback.
  - Implements stuck detection: `distance < 1.0` block movement over 3 cycles triggers `_unstuck` behavior (jump, dig forward, or teleport).
  - Validates action success (`_verify_action`) by checking inventory counts or position changes before and after execution.

### `game_interface.py`
- **Function**: Defines an abstract `GameEngineInterface` and implementes `MinecraftEngine` as a wrapper around the `MineflayerBridge`.
- **Design Decisions**:
  - Decouples Ernos's cognition loop from Mineflayer specifics, making the architecture theoretically extensible to other games (e.g. Terraria). Platform-agnostic `GameState` and `GameAction` classes.

### `mineflayer_bridge.py`
- **Function**: Manages the Python-to-NodeJS subprocess IPC.
- **Design Decisions**:
  - Starts `node mineflayer/bot.js` in a subprocess with `start_new_session=True` for clean teardown of children.
  - Uses JSON over stdin/stdout for bidirectional command execution/event listening.
  - Stderr is logged at WARNING/DEBUG for visibility into JS-side crashes.
  - Defines the core bridge commands (`goto`, `follow`, `collect`, `farm`, `place`, etc.) with appropriate timeouts.

### `knowledge_base.py`
- **Function**: Dynamic Minecraft knowledge base for resolving unknown items.
- **Design Decisions**:
  - Checks a local cache (`minecraft_knowledge.json`), then static `tech_tree`, then queries the LLM: `prompt = f"What is the Minecraft Java Edition crafting recipe for '{item}'?\n\n"`
  - Prevents blind "collect" actions for crafted items that aren't in the static tree.

### `planner.py`
- **Function**: `HierarchicalPlanner` decomposes high-level goals into ordered execution Steps (`SubGoal`).
- **Design Decisions**:
  - Checks inventory. If material is raw, generates `collect` or `find`/`mine` actions (checking tools). If material needs smelting, adds `smelt` action (and checks for furnace). If crafted, resolves recipe and checks for `crafting_table`.

### `skill_graph.py`
- **Function**: DAG for complex non-crafting goals (building, farming, exploring).
- **Design Decisions**:
  - Keeps a persistent graph in `memory/public/skill_graph.json`.
  - Uses an LLM to dynamically add missing prerequisites for new goals.

### `skill_library.py`
- **Function**: Voyager-style skill library. Stores successful action sequences to reuse them directly next time.
- **Design Decisions**:
  - Tracks `success_count`, `failure_count`, and `avg_duration`.

### `tech_tree.py`
- **Function**: Hardcoded logic rules for Minecraft recipes, smelting, raw materials, and pickaxe requirements.

### `utils.py`
- **Function**: Provides `mc_log`, `log_embodiment`, and `GAME_ACTIONS_ADDON`.
- **Design Decisions**:
  - `log_embodiment`: Pushes significant game events into the global `globals.activity_log` so Ernos can recall them out-of-game (Discord).
  - `GAME_ACTIONS_ADDON`: The massive system prompt appended to the LLM when operating in-game. Mandates exploration over strip-mining, day/night cycles, and the strict `ACTION:` and `PRECOGNITION:` dual-output format to power the Predictive Chain.

## Directory structure inside `src/gaming/`:
- `mineflayer/`: The Node.js bot implementation containing spatial reasoning, pathfinding, and action execution logic.
- `mindcraft_ref/`: (To be investigated - potentially a reference implementation).

*Next steps: Audit the JS bridge implementation (`mineflayer/`).*
