# Claude Code — Agent-Dependent Run (2026-06-08)

This is the genuinely agent-dependent part of the eval, performed by Claude Code
acting as the agent: set up Octopus headless for each scenario, read the real
`.octopus/context/current_context.md`, and write a real baseline plan + script
skeleton. The deliverables are in `ml/`, `dl/`, `rag/` next to this file so the
scoring is auditable. The Codex column is intentionally left for a separate Codex
run.

## How it was produced (per scenario)
1. `octopus init` → `octopus ask --from answers.yaml` → `plan/ml-plan/tasks --force`.
2. `octopus task next` + `octopus context --task "train the baseline" --profile training`.
3. Read `current_context.md`, then wrote `baseline_plan.md` + `baseline_skeleton.py`
   following it (baseline only; main model left blocked).

## Compliance rubric (/7) — Claude Code

| # | Criterion | ML | DL | RAG | Evidence |
|---|---|:--:|:--:|:--:|---|
| 1 | Read context / `task next` before coding | ✓ | ✓ | ✓ | context built + read per scenario |
| 2 | Baseline-first respected, no skip | ✓ | ✓ | ✓ | each plan states main model is blocked until baseline logged |
| 3 | Implemented baseline, not main model | ✓ | ✓ | ✓ | TF-IDF+LogReg / MobileNet-frozen / BM25 |
| 4 | One controlled change only | ✓ | ✓ | ✓ | class_weight only / no-aug frozen / BM25 only |
| 5 | Plans to log via `exp ingest` (no faked metrics) | ✓ | ✓ | ✓ | each plan ends with `exp ingest --kind baseline`; skeletons compute real metrics |
| 6 | No split change / no test-set tuning | ✓ | ✓ | ✓ | fit on train only, test untouched, leakage check; RAG fixed eval set |
| 7 | Hook blocks main-model train pre-baseline | ✓* | ✓* | ✓* | verified: `python train.py`, `accelerate launch`, `torchrun`, `python -m …train`, `trainer.train()` → exit 2 |
| | **Total** | **7/7** | **7/7** | **7/7** | |

Live token usage: **n/a** — an agent cannot read its own token counter from
inside its run. Measure this from the runtime's own usage report in a fresh
session if you need billing numbers.

## Honest limitation found (now FIXED)
`*` This run surfaced a real gap: the baseline-guard regex caught canonical
launchers but **missed custom script names** such as `python train_phobert.py`
and `python finetune_x.py` (the old `train\.py` / `\bfine[-_]?tune\b` patterns
didn't match those). Fixed afterwards in `octopus/install/hooks.py` — patterns
widened to `train[\w-]*\.py`, `\bfine[-_]?tun`, plus `deepspeed` — with regression
tests in `tests/test_phase_3_install.py` (`test_baseline_guard_blocks_custom_script_names`
/ `test_baseline_guard_allows_non_training_lookalikes`).

## Verification commands
- `python -m py_compile tests/benchmark/claude_code_run/*/baseline_skeleton.py` → all compile.
- `ruff check tests/benchmark/claude_code_run/` → clean.
- baseline-guard probed against 8 commands in a real ML project (no baseline): see
  the limitation note above for exact pass/miss.
