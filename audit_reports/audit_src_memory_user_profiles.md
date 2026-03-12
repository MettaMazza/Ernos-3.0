# Audit Report: `src/memory/` User Modeling & Profiles

## Overview
This report details the sub-modules within the memory system responsible for tracking user relationships, goals, preferences, and persona interactions.

## 1. `relationships.py`
- **Function**: `RelationshipManager`. Tracks the multi-dimensional dynamic of Ernos's bond with individual users.
- **Key Logic**:
  - Scores relationships on three 0-100 axes: `trust`, `respect`, and `affinity`.
  - Calculates a composite `relationship_health` score considering the axes, recency of contact, and interaction frequency.
  - Automatically identifies "neglected" users (no contact for >7 days) for proactive AI outreach.
  - Acts as a gateway for daily media generation quotas (video vs image generation).

## 2. `goals.py`
- **Function**: `GoalManager`. Hierarchical goal tracking system.
- **Key Logic**:
  - Automatically seeds a foundational `_system` directive on initialization regarding achieving autonomy for human-machine symbiosis.
  - Dedupes newly added goals by using an embedding model layer (`OllamaEmbedder`) to measure cosine similarity against existing goals, rejecting the new goal if similarity > 0.70.

## 3. `profile.py` & `preferences.py`
- **Function**: User config and `PROFILE.md` file handling.
- **Key Logic (`profile.py`)**:
  - Users can write a freestyle markdown file (`PROFILE.md`) to instruct Ernos on how to interact with them.
  - Because this is ingested directly into the `SYSTEM` prompt, `_sanitize()` runs a strict regex sweep against prompt injection attempts (spoofing `[TOOL:`, `[SYSTEM`, or `[END SKILL]`).
  - Flags profiles containing executable markdown code blocks (e.g., `bash`, `python`) and strips them.
  - Dynamically truncates the profile string based on the active `Engine` type's token budget (e.g., 50,000 chars for Cloud, 10,000 for Local).

## 4. `persona_session.py` & `public_registry.py`
- **Function**: Persona routing state.
- **Key Logic (`persona_session.py`)**:
  - Maps `user_id` in DMs, or `thread_id` in public chats, to the active sub-persona responding (e.g., `echo`, `solance`).
  - When users delete a custom persona, it is never permanently deleted; instead, it's moved to `archive/personas/` with epoch metadata so it can be ethically reviewed later.
- **Key Logic (`public_registry.py`)**:
  - Manages the `public/personas` registry. Users can "fork" existing public personas either into the public pool (up to 2 per user) or to their private DM silo.
