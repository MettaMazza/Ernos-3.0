# Audit Report: `src/memory/` Knowledge Graph

## Overview
The Knowledge Graph (KG) subsystem, built on Neo4j, serves as Ernos's Tier 3 structured reasoning layer. The code is split across `graph.py` (API), `graph_crud.py` (Writes/Reads), and `graph_advanced.py` (Maint/Learning) to handle growing complexity.

## 1. `graph.py`
- **Function**: The public interface for the Graph Database.
- **Key Logic**:
  - Operates in "STRICT MODE" where it purposefully crashes the bot if Neo4j is offline (`raise e` on connection failure), cementing the KG as a mandatory dependency.
  - Dynamically initializes Neo4j indices on startup corresponding to the 26 `GraphLayer` enums.
  - Passes node/relationship additions through a `ValidatorFactory` and `ValidationQuarantine` to enforce symbolic constraints based on the layer.

## 2. `graph_crud.py`
- **Function**: Execution of Cypher queries for creating and fetching nodes/edges.
- **Key Logic**:
  - Extremely rigorous about data attribution and privacy. Both `add_node` and `add_relationship` feature strict blockers (`logger.critical("IDENTITY_BLOCKED: ...")` and `return`) if `user_id` or `scope` metadata are missing. Orphaned or unscoped nodes are outright rejected from the graph.
  - `query_context`: Implements an aggressive filter mapping request scope capabilities to node visibility. A critical safeguard loops over returned results — if a `[PRIVATE]` node somehow leaks into a `PUBLIC` query context due to a cypher matching error, it triggers a `🚨 CRITICAL PRIVACY FAILURE` alert.
  - `wire_to_root`: Links all new entities to a `Root:LayerName` hub node (e.g. `Root:Narrative`), structuring the graph hierarchically.
- **Quote**:
  ```python
      # STRICT IDENTITY VALIDATION: Block orphaned nodes entirely
      if user_id is None:
          import traceback
          caller = traceback.extract_stack()[-3]  # Get caller info
          logger.critical(f"IDENTITY_BLOCKED: Node '{name}' rejected - missing user_id! Caller: {caller.filename}:{caller.lineno}")
          logger.critical(f"FIX: Pass user_id=<discord_user_id> or user_id=-1 for system data.")
          return  # BLOCK - do not store orphaned nodes
  ```

## 3. `graph_advanced.py`
- **Function**: Graph Autonomy, Neural Mimicry, and System Maintenance.
- **Key Logic**:
  - `strengthen_synapse`: Mimics Hebbian Learning. When the LLM correlates data across two different cognitive layers, a `[:SYNAPSE]` relationship is created between the layer roots. Repeated cross-layer hits increase its `strength`.
  - `decay_synapses`: Run by background daemons to simulate forgetting — it reduces synapse strength by `decay_rate` (10%) and prunes pathways that drop to 0, culling unused thought pathways.
  - `prune_orphan_nodes`: A garbage collection function that deletes non-infrastructure nodes lacking any relationships that are older than 30 days.
  - `bulk_seed`: Facilitates high-throughput ingestion of SYSTEM level data (e.g., from `science_db.json`), bypassing quarantine and scoping it permanently to `CORE` under `user_id=-1`.
