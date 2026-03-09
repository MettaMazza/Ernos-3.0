# ERNOS 24-HOUR OBSERVATION RUN
## Started: 2026-02-08 02:07 UTC → Ends: 2026-02-09 02:07 UTC

**Baseline:** Fresh cycle reset. All logs wiped at 02:09 UTC. Only data from this boot exists.

---

## Files to Examine After 24hrs

| File | What to Look For |
|------|-----------------|
| `ernos_bot.log` | Errors, warnings, engine failures, tool crashes |
| `session_error.log` | Unhandled exceptions, stack traces |
| `memory/core/working_memory.jsonl` | Conversation retention, context quality |
| `memory/core/timeline.jsonl` | Event logging, interaction frequency |
| `memory/core/system_turns.jsonl` | ReAct loop count, tool usage patterns |
| `memory/core/provenance_ledger.jsonl` | Source attribution accuracy |
| `memory/core/context_private.jsonl` | DM handling, scope isolation |
| `memory/public/timeline.jsonl` | Public interaction history |
| `memory/public/bridge.log` | Cross-persona communication |
| `memory/system/town_hall/history.jsonl` | Town Hall sessions, persona debates |
| `memory/system/town_hall/personas/*/context.jsonl` | Individual persona memory growth |
| `memory/users/*/reasoning_public.log` | Reasoning chain quality |
| `minecraft.log` | Gaming subsystem activity (if used) |

---

## Post-Run Investigation Checklist

### 🔴 Critical (Check First)
- [ ] **Crash Count** — Any restarts? Check `session_error.log` for stack traces
- [ ] **Unhandled Exceptions** — grep `ernos_bot.log` for `ERROR` and `CRITICAL`
- [ ] **Memory Leaks** — Did the bot slow down over time? Check log timestamps for increasing response times
- [ ] **Tool Failures** — grep for `Tool .* failed` or `Cognitive Engine Failure`
- [ ] **Scope Leaks** — Any private data appearing in public logs? Cross-check `context_private.jsonl` against `timeline.jsonl`

### 🟡 Subsystem Health
- [ ] **Cognition Engine** — ReAct loop completion rate (grep `Cycle Complete`)
- [ ] **Hippocampus** — Memory consolidation working? (`working_memory.jsonl` growing?)
- [ ] **Knowledge Graph** — Ontologist activity (grep `consult_ontologist`)
- [ ] **Pre-Processor** — Complexity routing accuracy (grep `Pre-Processor Complexity`)
- [ ] **Skeptic/Superego** — Defense triggers (grep `Skeptic` and `Superego`)
- [ ] **Town Hall** — Any persona sessions ran? Check `town_hall/history.jsonl`
- [ ] **Bridge** — Cross-persona messages in `bridge.log`?
- [ ] **Dream Consolidation** — Did any sleep cycles trigger? (grep `Dream Consolidation`)
- [ ] **Proactive Messaging** — Any autonomous outreach? (grep `proactive` or `outreach`)
- [ ] **Web Tools** — Search success rate (grep `search_web` and `browse_site`)
- [ ] **Social Graph** — New user relationships? Check `memory/users/` for new silos

### 🟢 Quality & Behavior
- [ ] **Response Quality** — Sample 5 interactions from `working_memory.jsonl`, rate naturalness
- [ ] **Persona Consistency** — If personas were used, check for identity bleed
- [ ] **Tool Selection** — Is Ernos choosing the right tools? Check `system_turns.jsonl`
- [ ] **Context Retention** — Multi-turn conversations maintaining coherence?
- [ ] **Proxy Reply System** — If used, check for admin instruction leaks (grep `PROXY REPLY MODE`)
- [ ] **Idle Behavior** — What did Ernos do during quiet periods? (grep `autonomous` or `idle`)

### 📊 Metrics to Capture
- [ ] Total interactions (count lines in `timeline.jsonl`)
- [ ] Unique users (count unique user IDs in `working_memory.jsonl`)
- [ ] Tool usage frequency (parse `system_turns.jsonl` for tool names)
- [ ] Average response time (diff timestamps between user msg and bot reply)
- [ ] Error rate (errors / total interactions)
- [ ] Memory growth (file sizes of all `.jsonl` files)

---

## Quick Investigation Commands

```bash
# Error summary
grep -c "ERROR\|CRITICAL" ernos_bot.log

# Total interactions
wc -l memory/core/timeline.jsonl

# Tool usage breakdown
grep -oP '"tool":\s*"\K[^"]+' memory/core/system_turns.jsonl | sort | uniq -c | sort -rn

# Unique users
grep -oP '"user_id":\s*"\K[^"]+' memory/core/working_memory.jsonl | sort -u | wc -l

# Scope leak check (private content in public logs)  
grep -i "private\|dm\|direct" memory/public/timeline.jsonl

# Memory file sizes
du -sh memory/core/*.jsonl memory/public/*.jsonl memory/system/town_hall/*.jsonl

# Town Hall activity
wc -l memory/system/town_hall/history.jsonl memory/system/town_hall/personas/*/context.jsonl

# Proxy reply usage
grep "Proxy reply sent" ernos_bot.log
```

---

**When you return after 24hrs:** Paste any observed issues or just say "report" and we'll run the full investigation together.
