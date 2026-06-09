# Octopus Issues From VSMEC Baseline Run

This note generalizes problems observed while using Octopus + Codex on the VSMEC
emotion-classification project. The goal is to turn one project run into reusable
Octopus fixes, not to document VSMEC-specific training details only.

## Token / Context Observations

- Octopus generated context was about 2,802 tokens.
- If the active session window is 200k tokens, that is about 1.4%.
- If the active session window is 128k tokens, that is about 2.2%.
- The full end-to-end workflow used more context than that because Codex also
  initialized Octopus, read files, edited scripts, installed dependencies, hit
  errors, retried commands, and inspected metrics.
- Practical session usage for this baseline run was likely much higher than the
  generated Octopus context alone. A direct, well-routed baseline path should use
  meaningfully less context than an exploratory run with repeated failures.

## Octopus Issues To Fix

### 1. `answers.yaml` schema is too easy to get wrong

Observed behavior: an answers file using nested keys such as `dataset` or
`baseline` could be accepted without a hard failure, but important project state
was not populated correctly. In one run, the project was effectively treated as
`software` instead of an ML project.

Needed improvements:

- Warn or fail on unknown top-level keys in `octopus ask --from`.
- Add `octopus ask --schema` or `octopus ask --example` so agents can generate a
  valid intake file without guessing.
- Consider a `--strict` mode for CI/agent usage.
- Print a concise summary after ingest showing the resolved `project_type`,
  `task_type`, `dataset_status`, `main_metric`, and `baseline_model`.

### 2. ML project inference should be more robust

Observed behavior: if `project_type` is missing or malformed, Octopus can fall
back to `software`, which then blocks or misroutes ML planning.

Needed improvements:

- Infer `machine learning` when fields like `task_type`, `main_metric`,
  `baseline_model`, `has_labels`, or `dataset_status` are present.
- If inference is ambiguous, fail with a targeted message instead of silently
  producing a software workflow.
- `octopus ml-plan` should explain exactly which state field prevents ML
  planning.

### 3. Task generation does not respect provided fixed splits

Observed behavior: Octopus generated a task like "Create train / validation /
test split" even when the project already had fixed split files.

Needed improvements:

- If `dataset_size_note` or structured intake mentions fixed train/valid/test
  files, generate "verify and persist provided split" instead of "create split".
- Track split status explicitly in project state, for example:
  `split_status: provided | needs_creation | unknown`.
- Include split file paths in `data_strategy.md` when provided.

### 4. Evaluation protocol is ambiguous for fixed validation sets

Observed behavior: generated guidance mixed fixed validation usage with
cross-validation language. For datasets that already provide train/valid/test,
the default protocol should be unambiguous.

Needed improvements:

- For fixed train/valid/test datasets, default to:
  - tune/select config on train + valid only,
  - keep test untouched,
  - optionally train final model on train + valid after config is frozen,
  - evaluate test once.
- If CV is recommended, specify whether it runs on train only or train+valid and
  why.
- Make final-test policy explicit in `experiment_plan.md` and
  `.octopus/context/current_context.md`.

### 5. `octopus status` timestamp is not human-readable

Observed behavior: status showed a raw timestamp such as `Last built:
1781028794`.

Needed improvements:

- Format timestamps as local datetime plus raw epoch only if needed.
- Example: `Last built: 2026-06-10 01:13:14 +07:00`.

## Project-Level Improvements Octopus Should Encourage

These are not all Octopus bugs, but Octopus should nudge projects toward them in
generated baseline context.

### Dependency management

The VSMEC run hit missing or version-sensitive dependencies:

- `joblib`
- `pandas`
- `scikit-learn`
- `openpyxl`

Octopus should recommend a minimal `requirements.txt` or `pyproject.toml` for
baseline scripts, especially when the baseline uses common ML libraries.

### Baseline script robustness

The run exposed avoidable baseline-script issues:

- accidental stray character at file start,
- deprecated or incompatible `LogisticRegression(multi_class=...)`,
- `solver="liblinear"` not suitable for direct multiclass behavior in the
  intended setup,
- final test evaluation trained only on train rather than optionally retraining
  on train+valid after config selection.

Octopus baseline skeletons should prefer modern, version-tolerant defaults and
make final-training policy configurable.

Suggested options for generated scripts:

- `--cv-on train`
- `--final-train-on train_valid`
- `--skip-cv`
- `--model-path` for evaluating a saved model without retraining every time

### Split leakage checks

Octopus should make duplicate and near-duplicate checks a first-class baseline
step:

- exact duplicate text across train/valid/test,
- normalized duplicate text across splits,
- optional near-duplicate checks for text datasets.

If duplicates exist across fixed splits, reported test scores may be optimistic.

### Classical text baselines

For text classification, Octopus should suggest a small baseline family before
deep models:

- TF-IDF + Logistic Regression,
- LinearSVC,
- SGDClassifier,
- ComplementNB,
- small grid over `C`, `ngram_range`, and `min_df`.

All tuning must stay on train/validation only. The test set should not influence
model selection.

### Vietnamese text preprocessing

For Vietnamese social-media classification, Octopus should suggest lightweight
preprocessing options without making them mandatory:

- Unicode normalization,
- URL/user mention normalization,
- emoji handling,
- char n-grams as a strong default,
- optional Vietnamese word segmentation for word n-grams.

## VSMEC Baseline Result Snapshot

Validation:

- Macro-F1: 0.5311
- Accuracy: 0.5569

Test:

- Macro-F1: 0.5757
- Accuracy: 0.5801
- Weighted-F1: 0.5839

These results are useful as a baseline reference, but future Octopus changes
should focus on making the setup path shorter, schema handling stricter, and
evaluation policy clearer.

## Proposed Direction: Two-Tier Workflow

The VSMEC run suggests Octopus should not force the full planning/context path
when the user only needs a quick, correct baseline score. A better design is a
two-tier workflow.

### 1. GSD fast baseline path

Use this when the goal is to get a baseline run quickly with low token and time
overhead.

The agent should need only a small command or prompt:

```text
Build and run a complete baseline:
- fixed train/valid/test files
- no test tuning
- k-fold on train or train+valid only when requested
- validation metrics
- optional final test
- save model, metrics, predictions, and manifest
```

This path should not require running `octopus plan`, `octopus ml-plan`,
`octopus tasks`, and full context generation every time. It should focus on a
small spec, a robust script, and artifacts.

### 2. Octopus checkpoint path

Use this after a real run exists, or when the project needs longer-term
experiment management:

```bash
octopus exp ingest --run-dir runs/... --kind baseline
octopus exp analyze E001
octopus exp profile
octopus exp next
```

In this mode, Octopus acts primarily as project memory, experiment registry, and
decision support rather than full orchestration for every baseline attempt.

### 3. Small baseline spec instead of long context

For fast baseline runs, generate or accept a compact `baseline_spec.yaml` around
30-60 lines:

```yaml
task: text_classification
text_col: Sentence
label_col: Emotion
metric: macro_f1
train: train_nor_811.xlsx
valid: valid_nor_811.xlsx
test: test_nor_811.xlsx
no_test_tuning: true
baseline:
  model: tfidf_logreg
  cv_folds: 5
```

The agent should read this spec and the baseline script, not the full generated
planning stack. The full Octopus context remains useful for longer projects,
but should not be mandatory for a simple baseline.

## Baseline Script Improvements

The VSMEC script flow should avoid retraining cross-validation every time the
user asks for test evaluation.

Suggested CLI shape:

```bash
python train_baseline.py --mode train-valid
python train_baseline.py --mode test --model-path runs/.../model.joblib
python train_baseline.py --skip-cv
python train_baseline.py --final-train train_valid --evaluate-test
```

Preferred evaluation flow:

1. Use CV or train/valid to select config.
2. Train final model on train + valid after the config is frozen.
3. Evaluate test once.
4. Never rerun CV only to evaluate test.

Generated baseline projects should include:

- `requirements.txt` or `pyproject.toml`
- `config/baseline.yaml`
- duplicate checks between train/valid/test
- `valid_predictions.csv`
- `test_predictions.csv`
- confusion matrix
- top error examples
- fixed random seed
- clear CLI modes for train/eval/test

## Octopus Product Improvements

Octopus should support a fast baseline command that does less, but does it
reliably:

```bash
octopus baseline --fast --run
```

or:

```bash
octopus baseline-fast
```

Target behavior:

- auto-detect common dataset layouts when possible,
- create or validate `baseline_spec.yaml`,
- generate a robust baseline script,
- run the baseline when requested,
- save model, metrics, predictions, and manifest,
- ingest the run into Octopus.

Other Octopus improvements:

- strict schema for `answers.yaml`; unknown keys should warn or fail,
- no "create train/val/test split" task when fixed splits already exist,
- add a `minimal-baseline` context profile around 500-1000 tokens,
- format `octopus status` timestamps as datetimes,
- avoid forcing agents to reread full context when the task is only to run or
  evaluate a baseline script.

## Agent Run Evaluation

The VSMEC agent run completed the job, but was not efficient enough.

What went well:

- built a complete baseline,
- avoided test-set usage until explicitly requested,
- ran real commands and fixed real errors,
- produced real validation/test metrics,
- ingested the experiment into Octopus,
- created model, metrics, and report artifacts.

What did not go well:

- Octopus accepted or mishandled bad intake schema too quietly,
- generated script had compatibility issues with newer scikit-learn,
- dependency file was missing, causing manual installs,
- test mode retrained CV and wasted time,
- interrupted/background runs required better state handling,
- token/time overhead was too high for a simple baseline objective.

Overall assessment:

- Completion: 7/10
- Efficiency: 5.5/10

Best direction for this repo: keep Octopus strong as memory, tracking, and
experiment governance, but add a "get shit done" fast path for baseline/model
training: small spec, strong script, clear commands, complete artifacts, and no
long context unless the project actually needs it.
