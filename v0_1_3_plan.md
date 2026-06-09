# v0.1.3 Plan And Implementation Notes

## Reasoning

The VSMEC run showed that Octopus was useful as project memory and experiment
tracking, but too heavy for a quick baseline. The most expensive failures were
not model quality problems; they were workflow problems:

- bad `answers.yaml` could silently produce wrong project state,
- ML projects could be misclassified as software,
- fixed train/valid/test datasets still got "create split" tasks,
- generated evaluation protocol mixed fixed validation with cross-validation,
- context was larger than needed for fast baseline work,
- status timestamps were hard to read.

For v0.1.3, I prioritized fixes that prevent wrong orchestration before adding a
full auto-training command. I did not implement `octopus baseline --fast --run`
yet because a reliable runner across text/image/tabular/RAG needs a clearer
artifact and dataset contract. Instead, this version adds the safer foundation:
strict intake, fixed-split-aware planning, a minimal context profile, and a
small `baseline_spec.yaml` generator.

## Implemented

### Strict headless intake

- `octopus ask --from answers.yaml` now rejects unknown top-level keys.
- Unknown nested `compute` keys are also rejected.
- Error output points users to `octopus ask --schema`.
- `octopus ask --schema` prints a valid example intake file.

Files changed:

- `src/octopus/cli/commands/ask.py`
- `src/octopus/cli/main.py`
- `tests/test_ask_non_interactive.py`

### Conservative ML inference

- If `project_type` is missing but ML fields are present, Octopus infers
  `machine learning`.
- If the user explicitly sets `project_type: software`, Octopus keeps that value.
- This avoids the VSMEC failure mode without overriding explicit user intent.

Files changed:

- `src/octopus/core/schemas.py`
- `src/octopus/cli/commands/ask.py`
- `tests/test_ask_non_interactive.py`
- `tests/test_ml_plan.py`

### Fixed split awareness

- `ProjectState.fixed_split_available` detects train/valid/test split notes.
- Task generation now emits "Verify and persist provided train / val / test
  split" instead of "Create train / val / test split" when fixed splits exist.
- Data and experiment plans now describe fixed split usage clearly.
- Test tuning is explicitly forbidden; final test is evaluated once after config
  selection.

Files changed:

- `src/octopus/core/schemas.py`
- `src/octopus/storage/task_store.py`
- `src/octopus/planners/ml_planner.py`
- `src/octopus/templates/data_strategy.md.j2`
- `src/octopus/templates/experiment_plan.md.j2`
- `tests/test_task_management.py`
- `tests/test_ml_plan.py`

### Minimal baseline context

- Added context profile `minimal-baseline`.
- It selects only baseline-critical requirements, baseline contract, split, and
  leakage sections.
- This supports the "GSD fast path" without forcing agents to read the full
  training context every time.

Files changed:

- `src/octopus/context/profiles.py`
- `src/octopus/cli/main.py`
- `tests/test_context.py`
- `docs/reference/cli.md`

Usage:

```bash
octopus context --task "train the baseline" --profile minimal-baseline --budget 1200
```

### Baseline spec fast-path foundation

- Added `octopus baseline-spec`.
- It generates `baseline_spec.yaml`, a compact contract for fast baseline runs.
- It auto-detects common split files in the project root.
- For text classification, it includes text/label defaults, Unicode normalization
  guidance, URL/mention normalization, and char n-gram preference.
- For fixed splits, it sets `cv_folds: 0` and `final_train: train_valid`.

Files changed:

- `src/octopus/core/paths.py`
- `src/octopus/planners/baseline_spec.py`
- `src/octopus/cli/commands/baseline_spec.py`
- `src/octopus/cli/main.py`
- `tests/test_baseline_spec.py`
- `docs/reference/files.md`
- `docs/reference/cli.md`

Usage:

```bash
octopus baseline-spec --force
```

Example output shape:

```yaml
task: text_classification
metric: macro_f1
no_test_tuning: true
data:
  fixed_split: true
  train: train_nor_811.xlsx
  valid: valid_nor_811.xlsx
  test: test_nor_811.xlsx
baseline:
  model: tfidf_logreg
  cv_folds: 0
  final_train: train_valid
```

### Human-readable status timestamp

- `octopus status` now formats context build time as a local ISO datetime
  instead of raw epoch seconds.

Files changed:

- `src/octopus/cli/commands/status.py`
- `tests/test_cli.py`

## Verification

Focused test group:

```bash
pytest tests/test_ask_non_interactive.py tests/test_task_management.py \
  tests/test_ml_plan.py tests/test_context.py tests/test_baseline_spec.py \
  tests/test_cli.py
```

Result:

```text
45 passed
```

Lint:

```bash
ruff check src tests --exclude tests/datasets
```

Result:

```text
All checks passed!
```

Full test suite:

```bash
pytest
```

Result:

```text
141 passed
```

## Not Implemented Yet

### `octopus baseline --fast --run`

This is still the ideal next step, but it needs a careful runner contract:

- dataset loader per task type,
- dependency generation,
- artifact layout,
- saved model/prediction contract,
- final train/test policy,
- duplicate check implementation,
- safe ingestion into Octopus.

Recommended next iteration:

1. Implement `octopus baseline --fast` to generate `baseline_spec.yaml` and a
   baseline script.
2. Implement `octopus baseline --fast --run` only for text classification first.
3. Save artifacts under `runs/baseline-*`.
4. Ingest the run automatically with `octopus exp ingest --kind baseline`.

### Stronger split metadata

Current fixed split detection reads `dataset_size_note`. A better schema would
add structured fields:

```yaml
split:
  status: provided
  train: train_nor_811.xlsx
  valid: valid_nor_811.xlsx
  test: test_nor_811.xlsx
```

This should replace heuristic note parsing in a later release.

## Release Notes Draft

v0.1.3 should be described as a workflow-quality release:

- stricter headless intake,
- ML inference for missing `project_type`,
- fixed-split-aware tasks and evaluation protocol,
- compact `minimal-baseline` context profile,
- new `baseline_spec.yaml` fast-path generator,
- readable status timestamps.
