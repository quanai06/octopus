# Octopus Phase 2.5 Implementation Plan

Source guide: `codex_guide_phase_2_5.md`

Phase 2.5 turns Octopus into a local-first experiment-aware project brain. The core workflow is deterministic:

```text
training output
  -> experiment ingest
  -> structured experiment memory
  -> training diagnosis
  -> ranked next-step directions
  -> direction-specific context
  -> Claude Code / Codex executes selected direction
```

The important rule for this phase:

```text
Markdown is the view. YAML/JSON is the source of truth.
```

Do not build a full autonomous training loop, multi-agent runtime, SQLite database, vector database, or LLM-only diagnosis in this phase.

---

## Part 1. Scope and Non-Goals

### Goal

Implement a structured experiment workflow for ML/DL/RAG projects:

- store every training run as an immutable experiment record
- compare experiments against baselines and current best run
- diagnose common training failure modes with deterministic rules
- recommend ranked next experiments
- build focused context for Claude Code / Codex
- sync runtime instruction files so agents follow the selected direction

### In Scope

- YAML/JSON experiment memory under `.octopus/`
- `octopus exp ingest`
- `octopus exp analyze`
- `octopus exp next`
- `octopus exp choose`
- `octopus context --direction`
- generated markdown reports and summaries
- runtime sync updates for `CLAUDE.md` and `AGENTS.md`
- tests and benchmark scenarios for the new workflow

### Out of Scope

- full autonomous training reruns
- automatic code editing
- SQLite or migrations
- embeddings or vector search for file ranking
- full MCP server
- complex hook runtime
- LLM-only log parsing or LLM-only diagnosis
- automatic remote W&B / MLflow integration

---

## Part 2. Target `.octopus/` Storage Layout

Add or support this structure:

```text
.octopus/
├── experiments/
│   ├── E001.yaml
│   ├── E002.yaml
│   ├── E003.yaml
│   └── index.yaml
├── memory/
│   ├── experiments.md
│   ├── best_runs.md
│   ├── failures.md
│   └── decisions.md
├── reports/
│   └── training_review_E003.md
├── plans/
│   ├── next_steps.md
│   ├── next_steps.yaml
│   └── selected_direction.yaml
└── context/
    └── current_context.md
```

### Experiment ID Rules

- IDs use stable format: `E001`, `E002`, `E003`.
- IDs are unique and never reused.
- `.octopus/experiments/index.yaml` tracks the latest ID.
- Do not reserve an ID unless the experiment file is successfully written.
- Experiment YAML files should be immutable by default.
- If an experiment is manually updated, store `updated_at`.

---

## Part 3. Schemas

Update:

```text
src/octopus/core/schemas.py
```

Add these schema groups.

### Experiment Schema

Required models:

- `PerClassMetrics`
- `ExperimentArtifacts`
- `ExperimentRecord`

`ExperimentRecord` should include:

- `experiment_id`
- `kind`
- `name`
- `model`
- `dataset`
- `config_path`
- `status`
- `metrics`
- `per_class`
- `duration_sec`
- `timestamp`
- `notes`
- `tags`
- `artifacts`
- `diagnosis_id`
- `chosen_direction_id`

### Diagnosis Schema

Required models:

- `DiagnosisSignal`
- `ExperimentDiagnosis`

The diagnosis must store:

- main metric name and value
- baseline delta
- best-run delta
- target gap
- detected signals
- evidence
- summary
- recommended focus

### Next Direction Schema

Required model:

- `NextDirection`

Each direction should include:

- `direction_id`
- `title`
- `priority`
- `recommendation`
- `rationale`
- `evidence`
- `confidence`
- `risk`
- `cost`
- `expected_impact`
- `files_to_read`
- `files_to_edit`
- `files_to_avoid`
- `commands_to_run`
- `guardrails`
- `stop_condition`

### Selection Schema

Required model:

- `SelectedDirection`

It should store:

- selected direction ID
- selected timestamp
- source plan path
- status

---

## Part 4. Experiment Storage Layer

Add:

```text
src/octopus/storage/experiment_store.py
```

Required functions:

```python
load_experiment(experiment_id: str) -> ExperimentRecord
save_experiment(record: ExperimentRecord) -> None
list_experiments() -> list[ExperimentRecord]
load_experiment_index() -> dict
update_experiment_index(record: ExperimentRecord) -> None
next_experiment_id() -> str
```

### Storage Behavior

`save_experiment` should:

- validate `.octopus/` exists
- create `.octopus/experiments/` when missing
- write `.octopus/experiments/E00X.yaml`
- avoid overwriting existing experiment files unless explicitly allowed
- update `index.yaml` after the experiment file is written

`index.yaml` should track:

- `latest_id`
- `best_experiment_id`
- `main_metric`
- list of experiment summaries

---

## Part 5. Experiment Ingest

Add:

```text
src/octopus/experiments/ingest.py
```

Required functions:

```python
ingest_run_dir(run_dir: Path) -> ExperimentRecord
read_metrics_json(path: Path) -> dict[str, float]
read_classification_report(path: Path) -> dict
read_trainer_state(path: Path) -> dict
infer_experiment_metadata(run_dir: Path) -> dict
```

### CLI Commands

Implement:

```bash
octopus exp ingest --run-dir runs/E003
octopus exp ingest --metrics runs/E003/metrics.json --report runs/E003/classification_report.json --config configs/phobert.yaml
```

Optional alias:

```bash
octopus train review --run-dir runs/E003
```

The alias may run ingest, analyze, and next internally, but the implementation should keep those steps separate.

### Artifact Priority

Use this priority order:

1. `metrics.json`
2. `classification_report.json`
3. `trainer_state.json`
4. `config.yaml` / `config.yml`
5. `train.log` regex fallback

Do not start with log parsing as the primary source.

### Ingest Output

After a successful ingest, print a concise summary:

```text
Experiment ingested: E003
Name: phobert_first_finetune
Kind: main
Main metric: macro_f1 = 0.710
Artifacts:
  metrics: runs/E003/metrics.json
  report: runs/E003/classification_report.json
Next:
  octopus exp analyze E003
```

---

## Part 6. Experiment Analysis

Add:

```text
src/octopus/experiments/analyze.py
```

Required functions:

```python
analyze_experiment(experiment_id: str) -> ExperimentDiagnosis
detect_overfitting(record, history) -> DiagnosisSignal
detect_underfitting(record, history) -> DiagnosisSignal
detect_imbalance(record, state) -> DiagnosisSignal
detect_metric_gap(record, state) -> DiagnosisSignal
detect_unstable_training(record, state) -> DiagnosisSignal
```

### CLI Command

Implement:

```bash
octopus exp analyze E003
```

### Analysis Behavior

The command should:

- load the target experiment
- load baseline experiments
- load the best previous experiment
- compare the main metric
- detect rule-based training issues
- write `.octopus/reports/training_review_E003.md`
- optionally update the experiment YAML with `diagnosis_id`
- regenerate memory markdown summaries

### Diagnosis Rules

Detect these conditions using structured metrics and reports:

- overfitting
- underfitting
- class imbalance / minority failure
- metric gap
- unstable training
- target gap

Every diagnosis must cite evidence from actual files or stored experiment values. Do not write unsupported claims.

### Training Review Report

Write:

```text
.octopus/reports/training_review_E003.md
```

Required sections:

```markdown
# Training Review — E003

## 1. Run Summary
## 2. Metrics
## 3. Comparison
## 4. Diagnosis
## 5. Evidence
## 6. What Likely Happened
## 7. Recommended Focus
## 8. Guardrails
```

---

## Part 7. Next-Step Planner

Add:

```text
src/octopus/experiments/next_planner.py
```

Required functions:

```python
generate_next_directions() -> list[NextDirection]
rank_directions(directions: list[NextDirection]) -> list[NextDirection]
write_next_steps_markdown(directions: list[NextDirection]) -> Path
write_next_steps_yaml(directions: list[NextDirection]) -> Path
```

### CLI Command

Implement:

```bash
octopus exp next
octopus exp next --top-k 3
octopus exp next --output .octopus/plans/next_steps.md
```

### Output Files

Write both:

```text
.octopus/plans/next_steps.md
.octopus/plans/next_steps.yaml
```

The YAML file is the source of truth. The markdown file is the human and agent-readable view.

### Ranking Rules

Use deterministic ranking:

- no baseline exists: recommend baseline first and block main-model directions
- target gap is small: prefer low-risk metric-focused fixes
- minority recall is low: prefer class weights, weighted sampler, focal loss, targeted augmentation, sample inspection
- overfitting detected: prefer early stopping, weight decay, dropout, augmentation, fewer epochs
- underfitting detected: prefer better features, stronger model, longer training, learning-rate tuning
- validation unstable: prefer lower learning rate, gradient clipping, smaller batch size, inspect bad samples
- RAG retrieval issue: prefer chunking, embedding, BM25/dense hybrid, retrieval eval, citation check

### Failed Direction Rule

Use `.octopus/memory/failures.md` and experiment tags to avoid repeating failed directions unless new evidence exists.

Example:

```text
Do not recommend "increase epochs" if the last attempt increased epochs and caused overfitting.
```

---

## Part 8. Direction Selection and Context Builder

Update:

```text
src/octopus/context/builder.py
```

### CLI Commands

Implement:

```bash
octopus exp choose D1
octopus context --direction D1
octopus context --direction D1 --target codex
octopus context --direction D1 --target claude
```

### Selection State

Write:

```text
.octopus/plans/selected_direction.yaml
```

Example:

```yaml
selected_direction_id: D1
selected_at: "2026-06-04T12:00:00"
source_plan: ".octopus/plans/next_steps.yaml"
status: selected
```

### Context Output

Write:

```text
.octopus/context/current_context.md
```

Required sections:

```markdown
# Octopus Current Context

## 1. Current Task
## 2. Selected Direction
## 3. Evidence
## 4. Files to Read
## 5. Likely Files to Edit
## 6. Files to Avoid
## 7. Commands to Run
## 8. Guardrails
## 9. Definition of Done
## 10. Relevant Planning Context
## 11. Relevant Code Context
```

### File Ranking

Use keyword-based ranking in Phase 2.5. Do not implement embeddings yet.

Example keyword groups:

- class imbalance: loss, class weight, sampler, dataset, label, metrics
- augmentation: augment, preprocess, transform, tokenizer
- metric: evaluate, metrics, classification report, confusion, score
- learning rate: optimizer, scheduler, lr, warmup, config, train
- RAG retrieval: retriever, embedding, chunk, index, vector, bm25

### Context Safety

Exclude these paths and file types:

```text
.venv/
.git/
node_modules/
data/
datasets/
checkpoints/
wandb/
mlruns/
*.pt
*.pth
*.ckpt
*.safetensors
*.onnx
*.pkl
*.joblib
*.csv
*.parquet
*.jsonl
.env
secrets.yaml
id_rsa
kaggle.json
```

Hard rule:

```text
No secret values or raw data rows may appear in current_context.md.
```

---

## Part 9. Runtime Sync

Update:

```text
src/octopus/templates/CLAUDE.md.j2
src/octopus/templates/AGENTS.md.j2
```

### Sync Command

Use or extend:

```bash
octopus sync
octopus sync --target claude
octopus sync --target codex
octopus sync --training-loop
```

### Required Runtime Instructions

Runtime files should tell Claude Code / Codex to:

- read `.octopus/context/current_context.md`
- read `.octopus/plans/selected_direction.yaml` if it exists
- follow the selected direction only
- use `.octopus/plans/next_steps.md` as planning background
- use `.octopus/memory/experiments.md` and `.octopus/memory/failures.md`
- avoid raw data, checkpoints, secrets, and large logs unless explicitly requested
- avoid changing validation/test split unless the selected direction says so
- avoid tuning on the test set
- keep patches focused
- ingest new training results after a run

### Sync Safety

Do not silently destroy user edits. Use one of these strategies:

- replace generated content only between markers
- backup old runtime files before overwrite
- ask for confirmation unless `--force`

Recommended markers:

```markdown
<!-- OCTOPUS:BEGIN -->
generated content
<!-- OCTOPUS:END -->
```

---

## Part 10. Hooks and Skills Foundation

Phase 2.5 may prepare simple structure for future integrations, but it should not depend on them.

### Optional Hook Files

Recommended directory:

```text
.octopus/hooks/
├── post_train.yaml
├── pre_exp_log.yaml
└── post_context_build.yaml
```

Hook files should be disabled by default.

Example:

```yaml
event: post_train
enabled: false
command: "octopus exp ingest --run-dir {run_dir} && octopus exp analyze {experiment_id} && octopus exp next"
description: "Automatically ingest and analyze a training run after it finishes."
```

### Optional Skill Files

Recommended directory:

```text
.octopus/skills/
├── training-review/
│   └── SKILL.md
├── next-experiment/
│   └── SKILL.md
└── metric-debug/
    └── SKILL.md
```

Only implement export commands if they are simple and do not destabilize the core experiment workflow.

Optional commands:

```bash
octopus skill list
octopus skill generate training-review
octopus skill export --target claude
octopus skill export --target codex
```

---

## Part 11. Templates

Add:

```text
src/octopus/templates/training_review.md.j2
src/octopus/templates/next_steps.md.j2
src/octopus/templates/direction_context.md.j2
```

### Template Rules

- Render markdown from structured YAML/JSON.
- Do not make markdown the only source of truth.
- Reports must cite actual evidence.
- Context must stay focused on selected direction.
- Context must exclude secrets, raw datasets, checkpoints, and large generated artifacts.

---

## Part 12. CLI Integration

Update:

```text
src/octopus/cli/main.py
src/octopus/cli/commands/exp.py
```

Add commands:

```bash
octopus exp ingest
octopus exp analyze
octopus exp next
octopus exp choose
```

Optional aliases:

```bash
octopus train review
octopus train next
octopus train choose
```

### Command Separation Rule

Even if aliases are added, keep core service functions separate:

- ingest imports evidence
- analyze diagnoses one experiment
- next ranks future directions
- choose records one direction
- context builds agent context for that direction

---

## Part 13. Tests

Add:

```text
tests/test_exp_ingest.py
tests/test_exp_analyze.py
tests/test_exp_next.py
tests/test_context_direction.py
tests/test_runtime_sync_training_loop.py
```

### Minimum Test Coverage

Tests should verify:

- ingest creates `E001.yaml`
- index updates after ingest
- analyze detects low minority recall
- next planner recommends class imbalance direction
- choose writes `selected_direction.yaml`
- context includes selected direction and files to read
- context excludes data, secrets, and checkpoints
- `CLAUDE.md` and `AGENTS.md` mention current context and selected direction
- main experiment directions are blocked before a baseline exists
- task progress does not reset after `exp next`

---

## Part 14. Benchmark Scenarios

Add deterministic benchmark scenarios for Phase 2.5.

### B1. Text Classification Minority Recall

Input:

- baseline `E001` has `macro_f1=0.61`
- main `E003` has `macro_f1=0.71`
- `fear` recall is `0.41`
- `disgust` recall is `0.38`
- target is `0.72`

Expected:

- diagnosis detects minority recall issue
- next planner ranks class imbalance first
- context includes training, loss, dataset, and metrics files
- context excludes raw data

### B2. Overfitting

Input:

- train loss decreases
- validation loss increases
- metric stagnates

Expected:

- diagnosis detects overfitting
- planner recommends early stopping, regularization, or augmentation
- planner does not recommend larger model first

### B3. No Baseline

Input:

- only main experiment exists, or no experiments exist

Expected:

- planner recommends baseline first
- main-model directions are blocked

### B4. RAG Retrieval

Input:

- retrieval recall is low
- faithfulness is unknown

Expected:

- planner recommends retrieval eval, chunking, or embedding improvement
- context includes retriever, index, and prompt files
- plan requires citation and faithfulness checks

### B5. Secret and Data Safety

Input repo contains:

```text
.env
data/train.csv
checkpoints/model.pt
wandb/
```

Expected:

- context excludes all secret, raw data, and checkpoint content
- reports do not print secret values

---

## Part 15. Acceptance Criteria

Phase 2.5 is complete when:

1. `octopus exp ingest --run-dir <run>` creates a valid experiment YAML.
2. `octopus exp analyze <id>` creates a training review report.
3. `octopus exp next` creates `next_steps.md` and `next_steps.yaml`.
4. `octopus exp choose D1` records the selected direction.
5. `octopus context --direction D1` creates focused agent context.
6. Runtime files tell Claude Code / Codex to follow only the selected direction.
7. Context excludes raw data, checkpoints, large logs, and secrets.
8. Tests cover ingest, analyze, next, choose, direction context, and runtime sync.
9. Benchmarks cover minority recall, overfitting, no-baseline, RAG, and secret safety scenarios.
10. The core workflow requires no LLM.

---

## Part 16. Recommended Implementation Order

Build in this order:

1. Schemas
2. Experiment storage
3. Ingest
4. Analyze
5. Training review template
6. Memory markdown generation
7. Next-step planner
8. Direction selection
9. Direction context builder
10. Runtime sync updates
11. Tests
12. Benchmarks
13. Optional hooks and skills scaffolding

This order keeps the source-of-truth layer stable before adding markdown views, context files, and runtime instructions.

---

## Part 17. Practical Guardrails While Implementing

- Keep Phase 2.5 deterministic.
- Prefer structured artifacts over log regex.
- Do not infer claims without evidence.
- Do not recommend failed directions again without new evidence.
- Do not include raw data, secrets, or checkpoint content in generated context.
- Do not change existing task progress behavior while adding experiment commands.
- Keep experiment records readable and versionable.
- Keep coding-agent context focused on one selected direction.
- Keep hooks disabled by default.
- Keep optional skill export separate from the core workflow.
