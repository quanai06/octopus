# Concepts

The mental model behind Octopus.

## Baseline-first

The core rule: **establish a simple, reproducible baseline before any main-model
work.** Octopus enforces this, not just suggests it:

- `octopus exp log --kind main|candidate` is **blocked** until a completed
  baseline exists.
- Task `T020` (main model) **depends on** `T012` (baseline logged); `octopus task
  start T020` fails until the baseline is logged.
- When installed into a runtime, a **baseline-guard hook** blocks shell commands
  that look like main-model training (`python train.py`, `torchrun …`,
  `fine-tune …`) before a baseline exists (exit code 2).

Logging/ingesting a completed baseline marks `T010`/`T011`/`T012` done and
unblocks `T020`.

The baseline is a **full, data-type-aware train/eval protocol**, not a single
random holdout. `octopus ml-plan` renders a "Split & Cross-Validation" section
(in `data_strategy.md` and `experiment_plan.md`) chosen by task type:

- all tasks → use the canonical cleaned dataset/corpus only, and log raw path,
  cleaned path, schema, version/hash, and split/fold/query manifests;
- classification / DL classification → **StratifiedKFold** (k=5) when feasible,
  report mean ± std + per-class recall; for expensive DL, log the exception and
  use >=3 fixed-seed stratified runs;
- tabular regression → **KFold** (GroupKFold when rows share an entity);
- forecasting / time-ordered → **TimeSeriesSplit** (temporal, never shuffle);
- retrieval / RAG → **fixed labeled query eval set**, documented chunking grid,
  fixed top-k grid, Recall@k / MRR / source-hit, and reranking only as a later
  controlled change over a recorded candidate pool;
- recommendation → **time-aware split** on future interactions.

Preprocessing is fit inside each fold (leakage-safe), the held-out test set stays
untouched, and metrics are reported as mean ± std across folds.

## `.octopus/` is the source of truth

All state lives in `.octopus/` as YAML/JSON, with human-readable Markdown *views*
generated from it. Files, not a database — so both humans and agents can read it,
it commits to git, and it survives a context reset. See
[Generated files](reference/files.md).

## Context compression

`octopus context` builds `.octopus/context/current_context.md`: a task-focused
slice of the planning docs plus relevant code, kept under a token budget — instead
of pasting every document. Profiles tune what gets included:

- `planning`, `training`, `debugging`, `review`.

A *direction* context (`octopus context --direction D1`) is even smaller: just the
selected next step, its evidence, guardrails, and relevant code.

## Experiment memory vs session memory

- **Experiment memory** (`.octopus/experiments/`, `.octopus/memory/`) — the
  long-term archive of every run, best runs, failures, and decisions.
- **Session memory** (`.octopus/session/`) — short-term RAM for the *current*
  session (current task, selected direction, last run, recent events). Restored
  with `octopus resume` after a context reset. See
  [Resume](guides/resume-session.md).

## Baseline intelligence

After a baseline is logged, Octopus characterizes it deterministically:

- `octopus exp profile` → standing vs target, bias/variance, weak classes,
  data-quality flags, and **ranked techniques** (plus a "Do Not Try Yet" list).
- The technique knowledge lives in one place
  (`octopus.experiments.technique_library`) and is domain-aware
  (classification / regression / rag / generic).
- `octopus exp next` turns diagnosed symptoms into ranked next directions drawn
  from that same library.

## Host-runtime architecture (GSD-style)

Octopus is the deterministic **brain + guardrails**; the AI runtime (Claude Code
or Codex) runs the LLM loop.

```text
You / runtime
   │  /octopus-* slash command or prompt router
   ▼
Octopus CLI (deterministic)  ──►  .octopus/ file-state
   │
   ├─ command routers   → installed into ~/.claude/commands, ~/.codex/prompts
   ├─ subagents (Claude) → ~/.claude/agents/octopus-*
   └─ baseline-guard hook → ~/.claude/settings.json (PreToolUse)
```

`octopus install` projects these artifacts into each runtime. Octopus itself
never calls an LLM — everything it does is rule-based and reproducible.
