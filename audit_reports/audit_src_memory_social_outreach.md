# Audit Report: `src/memory/` Social & Outreach Subsystems

## Overview
This report covers the components responsible for mapping the social topology (Mycelium Network), handling validation exceptions (Quarantine), and orchestrating proactive AI-to-user messaging (Outreach & Inbox).

## 1. `quarantine.py`
- **Function**: `ValidationQuarantine`. Acts as a holding cell for facts that fail `LayerValidator` checks (e.g. missing a `user_id` for a `SOCIAL` fact). Safety/Moral violations are never quarantined; they are hard-dropped.
- **Key Logic**:
  - Maintains a queue capped at 2000 items. Upon hitting the cap, it triggers `_auto_triage()` which discards malformed facts (junk predicates > 50 chars), evicts stale entries older than 7 days, and attempts to automatically fix missing ownership tags by assigning `user_id=-1` (System) if applicable.

## 2. `social_graph.py`
- **Function**: `SocialGraphManager` (v3.3 Mycelium Network).
- **Key Logic**:
  - Automatically records when users mention each other (`record_mention`) and tracks co-occurrence in the same channels (`record_co_occurrence`).
  - Writes `MENTIONED` relationships directly into the Neo4j Knowledge Graph, creating a localized network topology to help the AI understand group dynamics and shared contexts between humans.

## 3. `outreach.py`
- **Function**: `OutreachManager`. Coordinates proactive messaging from Ernos or the sub-personas.
- **Key Logic**:
  - **AI Timing Decision**: Uses the core LLM Engine via `_ai_outreach_decision`. It prompts the model with the user's frequency preference, hours since last contact, and relationship strength. The model replies with a strict `YES` or `NO` to authorize the outreach.
  - **Routing Policy**: Respects strict scope policies per persona. `public` triggers a mention in public chat. `private` routes the message to the user's private `InboxManager`. A "Town Hall Only" restriction prevents background sub-personas from DMing users directly.

## 4. `inbox.py`
- **Function**: `InboxManager`. A per-user persistent message queue (`memory/users/{uid}/inbox.json`).
- **Key Logic**:
  - Manages asynchronous messages from sub-personas to users.
  - Users can set permissions per persona: `notify` (bot actively DMs the user), `normal` (message sits silently in the queue until the user checks `/inbox`), or `mute` (blocks the persona entirely).
