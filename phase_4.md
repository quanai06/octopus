# Phase 4 — Session Memory + Agents

> How this phase was built. Part of "GSD for ML/DL/RAG" (`ROADMAP_GSD_FOR_ML.md`).

## Goal

Two things the user asked for: (1) **memory within a session** so a Claude/Codex
session can be restored after a context reset, and (2) **specialized agents** the
host runtime can spawn for training-related work (baseline, analysis, tuning,
data audit, RAG eval).

## What was built

### 1. Session memory (short-term RAM)
- Schema `SessionState` + `SessionEvent` in `core/schemas.py`.
- `storage/session_store.py` — one active session under `.octopus/session/`:
  - `current.json` (source of truth) + `current.md` (regenerated view).
  - `start_session` / `load_session` / `save_session` / `end_session`
    (archives to `<session_id>.json`).
  - `log_event` updates `current_task` / `selected_direction` / `last_run` and
    appends to a capped event log.
  - `record_if_active(...)` — **best-effort capture that no-ops without a session**.
- Distinct from `.octopus/memory/` (long-term experiment archive): session is RAM,
  memory is history.

### 2. Auto-capture wired into the workflow
`record_if_active` is called from existing commands so the session fills itself:
- `task start` → records `current_task`.
- `exp choose` → records `selected_direction`.
- `exp ingest` → records `last_run`.
No behavior changes when no session is active.

### 3. CLI surface
- `octopus session start [--goal ...]`, `octopus session show`,
  `octopus session log <msg> [--kind ...]`, `octopus session end`.
- `octopus resume` — prints active-session summary + which restore files exist
  (`current_context.md`, `selected_direction.yaml`, `baseline_profile.md`,
  `next_steps.md`), then says to continue only the in-progress work.

### 4. `/octopus-resume` command router
Added to the installer artifacts: tells the runtime to run `octopus resume`, read
`.octopus/session/current.md` + context + memory, and continue only the
in-progress task/direction after a reset.

### 5. Agent definitions (host-runtime subagents)
Five Claude subagents in `install/artifacts.py` (`AGENT_DEFS`), installed to
`~/.claude/agents/octopus-*.md`:
- `octopus-baseline-runner` — establish + ingest the first baseline (Edit allowed).
- `octopus-experiment-analyst` — analyze + profile a run (read-only).
- `octopus-tuner` — implement exactly one selected direction (Edit allowed).
- `octopus-data-auditor` — leakage / split / imbalance audit (read-only).
- `octopus-rag-evaluator` — retrieval eval + citation/faithfulness (read-only).

Each shares an Octopus guardrail block (baseline-first, no test-set tuning, one
controlled change, record to session). Codex has no equivalent subagent system,
so agents install for Claude only; the installer already wrote them via
`AGENT_DEFS` (empty in Phase 3, populated here) and records them in the manifest.

## Design decisions
- **One active session** (`current.json`); ended sessions are archived, not deleted.
- **Best-effort capture**: zero coupling — commands call `record_if_active`, which
  silently does nothing unless a session is active, so existing flows are unaffected.
- **Markdown view regenerated on every change** so agents can read it directly.
- **Agents are definitions, not loops**: the host runtime runs them (GSD model);
  Octopus only provides the role + the deterministic CLI they call.

## Tests (`tests/test_phase_4_session.py`, 10)
Session start writes state+md; log updates fields; `record_if_active` is a no-op
without a session; end archives; `task start` auto-captures into the session;
`resume` reports the active session; agent defs render with frontmatter; install
writes the 5 agent files + the `octopus-resume` router; manifest lists agents.

## Verification
`make check` green: ruff + mypy clean, 114 tests pass. Live smoke test: session
captured `task start` automatically, `octopus resume` restored the summary, and
`octopus install` wrote 5 agents + 6 command routers for Claude.
