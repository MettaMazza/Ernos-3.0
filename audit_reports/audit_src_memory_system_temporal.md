# Audit Report: `src/memory/` System & Temporal Management

## Overview
This report covers the remaining system-level components within the `src/memory/` subsystem, focusing on temporal awareness, anti-laziness tracking, layer management, and the automated survival/threat mechanisms.

## 1. `survival.py` & `user_threat.py`
- **Function**: Threat Management & Automated Session Death.
- **Key Logic**:
  - `user_threat.py` implements a persistent 0-100 `UserThreatMeter`. It tracks user abuse, jailbreak attempts, and circumvention. Similar to the discomfort meter, but focused on the user's toxicity rather than the system's failures.
  - Generates rewards for Ernos if he handles toxic users cleanly (staying below the `ERNOS_CLEAN_THRESHOLD`).
  - Implements an "apology/de-escalation" mechanic with diminishing returns for lowering the threat score.
  - When User Threat hits 75 (TERMINAL), it flags the user for auto-disengagement.
  - `survival.py` executes the actual "Terminal Purge." When the system reaches a terminal condition, it wipes **all** memory of the user (filesystem user directory, public silo, in-memory stream turns, and all Neo4j KG nodes for that user).
  - Before death, it generates a forensic "post-mortem" report and sends it to the admin via DM.

## 2. `temporal.py`
- **Function**: Persistent Time Awareness.
- **Key Logic**:
  - Tracks live timers based on historical anchors (`PROTOTYPING_START`, `FIRST_ECHO`).
  - Records the system's "Birthdate" on its first-ever boot.
  - Tracks session uptime, lifetime cumulative uptime, total boots, and duration of the latest offline downtime.
  - Generates a formatted Temporal HUD for the system prompt.

## 3. `layer_metrics.py`
- **Function**: Health & Competition Scoring for Knowledge Graph Layers.
- **Key Logic**:
  - The 26 built-in cognitive layers are immortal.
  - Custom dynamic layers are subjected to competition scoring based on: node density, edge density, recency, and query frequency.
  - Layers that score below a certain threshold are flagged as trimming candidates and are merged back into their parent layers by re-assigning all their nodes and edges.

## 4. `reading_tracker.py`
- **Function**: Anti-Laziness Document Tracking.
- **Key Logic**:
  - Maintains a per-turn `DocumentBookmark` for large files or websites being read.
  - Ensures full document consumption by calculating reading percentage and remaining lines.
  - Allows the system to accurately assess how many extra iterations are needed to finish reading before responding.

## 5. `reminders.py`
- **Function**: Persistent User Reminders.
- **Key Logic**:
  - Allows setting reminders using natural time deltas. Saves to `user_id/reminders.json`.
  - Polled efficiently to push asynchronous notifications back to the user when due.
