# Octopus Roadmap — "GSD for ML/DL/RAG"

## Vision

Octopus = the GSD (Get Shit Done) pattern, specialized for ML/DL/RAG.
Instead of forcing a code-delivery workflow, Octopus forces a
**baseline-first → understand-the-baseline → disciplined-tuning** workflow,
and embeds into Claude Code + Codex so users are prompted in the right
direction with low token cost.

Octopus stays the deterministic Python "brain" (tools + file-state). The GSD
upper layers (commands, agents, installer, hooks) get added on top.

## Architecture mapping (GSD -> Octopus)

| GSD layer            | Octopus today            | To add                                   |
|----------------------|--------------------------|------------------------------------------|
| File-state `.planning/` | `.octopus/` (done)    | `.octopus/session/` (session memory)     |
| Tools (SDK/CLI)      | Python CLI (done)        | keep as the brain                        |
| Agent layer          | none                     | ML-specialized agent markdown defs       |
| Command/skill layer  | static CLAUDE/AGENTS.md  | `/octopus-*` slash-command routers       |
| Installer            | renders files in project | `octopus install --runtime claude,codex` |
| Hooks                | none                     | baseline-guard, context-monitor, scan    |
| Model profiles       | none                     | per-agent tier routing                   |

## Decisions (locked 2026-06-08)

- **Agent model:** host-runtime driven (GSD style). Agents are markdown
  definitions installed into Claude Code / Codex; the host runtime runs the
  LLM loop. Octopus provides definitions + deterministic CLI tools. No API key.
- **Runtimes:** Claude Code **and** Codex, first-class for both.
- **Start:** Track 0 (foundation) first.

## Roadmap

### Track 0 — Foundation  ✅ DONE (2026-06-08)
- [x] Fix mypy error in `next_planner.py` (clean type narrowing).
- [x] `Makefile` with `check` = ruff + mypy + pytest.
- [x] `tests/benchmark/` — promoted the ad-hoc Phase 2 eval into a repeatable
      pytest suite (4 scenarios x flow/artifacts/token-savings). 71 tests pass.

### Phase 3 — Installer + Command layer  (next)
- `octopus install --runtime claude,codex`: write slash-command routers into
  `~/.claude/commands` and `~/.codex`, plus agent defs and hooks.
- Thin command routers (low token surface): `/octopus-plan`, `/octopus-train`,
  `/octopus-tune`, `/octopus-resume`.
- Hook `baseline-guard`: block main-model edits/training before a baseline.
- Multi-runtime projection (namespace + tool-name + path differences).

### Phase 4 — Session memory + Agents
- `.octopus/session/<id>.md`: short-term RAM for the active session (current
  task, selected direction, last ingested run, in-session decisions).
- `/octopus-resume` reads session + `.octopus/memory/` after context reset.
- Agent definitions: `octopus-baseline-runner`, `octopus-experiment-analyst`,
  `octopus-tuner`, `octopus-data-auditor`, `octopus-rag-evaluator`.

### Phase 5 — Baseline intelligence  ✅ DONE
- [x] Symptom -> technique library (`experiments/technique_library.py`):
      domain-aware (classification / regression / rag / generic) catalog mapping
      diagnosed symptoms to techniques, ranked by leverage/cost/risk, plus
      anti-patterns ("Do Not Try Yet").
- [x] `octopus exp profile` + `baseline_profile.py` + `BaselineProfile` schema:
      after baseline ingest, characterize standing vs target, bias/variance,
      headroom, weak classes, data-quality flags, and ranked techniques.
      Writes `.octopus/reports/baseline_profile.md`. Wired into CLAUDE/AGENTS
      runtime templates so agents profile before tuning. (tests: `test_phase_5.py`)
- [x] Auto-ingest from MLflow / W&B / TensorBoard run dirs (`experiments/trackers.py`,
      `exp ingest --tracker auto|mlflow|wandb|tensorboard|none`). MLflow/W&B parsed
      from disk with no extra dependency; TensorBoard via optional `tensorboard`.
      (tests: `test_phase_5_trackers.py`)
- [x] Refactored `next_planner.py` to draw directions from the technique library:
      symptom-level direction frames filled with ranked techniques + guardrails;
      "What is unlikely" now uses `antipatterns_for`. Knowledge lives in the library.

Phase 5 complete. Remaining ideas for later: optional LLM enrichment of
rationales (Phase 6), and a `next_steps.md` section that lists the full ranked
technique table per direction.

### Phase 6 — Model profiles + optional LLM-assist
- Per-agent tier routing (quality/balanced/budget).
- Optional `--llm` flag to enrich `exp suggest` rationales; deterministic core
  remains the source of truth.

## Guarantees to preserve at every phase
- Deterministic core; YAML/JSON is source of truth, markdown is a view.
- Baseline-first enforcement stays a hard gate, now also at runtime via hooks.
- Token efficiency (context compression) — benchmarked in `tests/benchmark/`.
- `make check` green before every commit.
