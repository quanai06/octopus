# Phase 2.5 Implementation Notes

Source guide: `codex_guide_phase_2_5.md`

## Summary

Phase 2.5 upgrades Octopus from simple experiment logging into a deterministic, local-first experiment memory workflow:

```text
experiment ingest -> structured memory -> training analysis -> ranked next directions -> selected direction context
```

Markdown files are generated views. YAML files remain the source of truth.

## Implemented

- Added Phase 2.5 schemas in `src/octopus/core/schemas.py`:
  - `PerClassMetrics`
  - `ExperimentArtifacts`
  - extended `ExperimentRecord`
  - `DiagnosisSignal`
  - `ExperimentDiagnosis`
  - `NextDirection`
  - `SelectedDirection`
- Extended experiment storage in `src/octopus/storage/experiment_store.py`:
  - reads legacy `exp_*.yaml` and new `E*.yaml`
  - keeps old `exp log` IDs compatible
  - allocates new ingest IDs as `E001`, `E002`, ...
  - updates `.octopus/experiments/index.yaml`
- Added deterministic ingest in `src/octopus/experiments/ingest.py`:
  - reads `metrics.json`
  - reads `classification_report.json`
  - reads `trainer_state.json`
  - reads `config.yaml` / `config.yml`
  - uses train log regex only as fallback
- Added rule-based analysis in `src/octopus/experiments/analyze.py`:
  - overfitting
  - underfitting
  - class imbalance / minority recall
  - metric gap
  - unstable training
  - target gap evidence
- Added training review output:
  - `.octopus/reports/training_review_E001.md`
- Added memory markdown views:
  - `.octopus/memory/experiments.md`
  - `.octopus/memory/best_runs.md`
  - `.octopus/memory/failures.md`
  - `.octopus/memory/decisions.md`
- Added next-step planner in `src/octopus/experiments/next_planner.py`:
  - writes `.octopus/plans/next_steps.yaml`
  - writes `.octopus/plans/next_steps.md`
  - ranks directions with deterministic rules
- Added direction selection in `src/octopus/experiments/selection.py`:
  - writes `.octopus/plans/selected_direction.yaml`
  - appends selected decisions to `.octopus/memory/decisions.md`
- Added direction context support:
  - `octopus context --direction D1`
  - `octopus context --direction D1 --target codex`
  - `octopus context --direction D1 --target claude`
- Updated runtime templates:
  - `CLAUDE.md` tells Claude Code to follow selected direction only
  - `AGENTS.md` tells Codex to read current context, next steps, selected direction, and experiment memory
- Added sync backup behavior before regenerating runtime files.
- Added Phase 2.5 tests in `tests/test_phase_2_5.py`.

## New Commands

```bash
octopus exp ingest --run-dir runs/E001
octopus exp ingest --metrics runs/E001/metrics.json --report runs/E001/classification_report.json --config runs/E001/config.yaml
octopus exp analyze E001
octopus exp next
octopus exp next --top-k 3
octopus exp choose D1
octopus context --direction D1 --target codex
```

## Safety Rules Added

- Context excludes `.venv/`, `.git/`, `node_modules/`, raw data directories, checkpoints, model weights, logs, `.env`, `secrets.yaml`, `id_rsa`, and `kaggle.json`.
- Direction context says not to read or copy raw data rows, secrets, checkpoints, or large logs.
- Next-step planner blocks main-model work when no completed baseline exists.
- Runtime instructions tell agents to implement only the selected direction and avoid changing validation/test split unless explicitly selected.

## Compatibility

Legacy commands are still supported:

```bash
octopus exp log
octopus exp list
octopus exp compare
octopus exp diagnose
octopus exp suggest
octopus exp report
```

Legacy `octopus exp log` keeps using `exp_001` style IDs. New `octopus exp ingest` uses `E001` style IDs.
