# Codex Guide — Octopus Phase 2.5

> Goal: Implement the next practical phase of Octopus as an **Experiment Memory + Training Review + Next-Step Planner + Direction Context** system.
>
> This phase should stay deterministic and local-first. Do **not** jump directly into complex multi-agent workflows, SQLite, or LLM-based autonomous training loops. Build the structured experiment workflow first.

---

## 0. Phase 2.5 Positioning

Octopus currently works as a planning CLI and workflow guard for ML/DL/RAG projects.

Phase 2.5 upgrades Octopus into an **experiment-aware project brain**:

```text
training output
   ↓
experiment ingest
   ↓
structured experiment memory
   ↓
training analysis / diagnosis
   ↓
ranked next-step directions
   ↓
direction-specific context for Claude Code / Codex
   ↓
user chooses direction
   ↓
Claude Code / Codex executes within guardrails
```

Octopus should not replace Claude Code or Codex.

Claude Code / Codex are executors.

Octopus should become the layer that remembers experiments, compares runs, diagnoses common training failure modes, proposes next controlled experiments, and compiles the exact context needed for a coding agent to implement the selected direction.

---

## 1. Experiment Memory

### 1.1 Purpose

Experiment Memory is the source of truth for previous training runs.

It should answer:

- What baseline has been tried?
- What model is currently best?
- What metrics were achieved?
- Which directions already failed?
- Which config, dataset, and artifacts produced each result?
- What should the next experiment compare against?

This memory must be structured, versionable, easy to inspect, and readable by coding agents.

### 1.2 Storage Format

Use YAML/JSON files, not SQLite, for Phase 2.5.

Reason:

- Easy to inspect manually
- Easy for Claude Code / Codex to read
- Fits the current `.octopus/` file-based architecture
- No migration system needed yet
- Good enough for tens or hundreds of experiments

Recommended structure:

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
│   └── next_steps.md
└── context/
    └── current_context.md
```

### 1.3 Experiment ID Policy

Use stable experiment IDs:

```text
E001
E002
E003
...
```

Rules:

- IDs must be unique.
- IDs must not be reused.
- `index.yaml` tracks the latest ID.
- If ingest fails halfway, do not reserve the ID unless the experiment file is written successfully.
- Experiments should be immutable by default. If edited, store `updated_at`.

### 1.4 Experiment Schema

Add or extend Pydantic schemas.

Recommended model:

```python
from typing import Literal
from pydantic import BaseModel, Field


class PerClassMetrics(BaseModel):
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    support: int | None = None


class ExperimentArtifacts(BaseModel):
    run_dir: str | None = None
    log_path: str | None = None
    metrics_path: str | None = None
    report_path: str | None = None
    config_path: str | None = None
    checkpoint_path: str | None = None


class ExperimentRecord(BaseModel):
    experiment_id: str
    kind: Literal["baseline", "candidate", "main", "ablation", "debug", "unknown"] = "unknown"
    name: str
    model: str | None = None
    dataset: str | None = None
    config_path: str | None = None
    status: Literal["completed", "failed", "running", "unknown"] = "unknown"

    metrics: dict[str, float] = Field(default_factory=dict)
    per_class: dict[str, PerClassMetrics] = Field(default_factory=dict)

    duration_sec: float | None = None
    timestamp: str | None = None
    notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    artifacts: ExperimentArtifacts = Field(default_factory=ExperimentArtifacts)

    diagnosis_id: str | None = None
    chosen_direction_id: str | None = None
```

Example YAML:

```yaml
experiment_id: E003
kind: main
name: phobert_first_finetune
model: phobert-base
dataset: vie_emotion_v1
config_path: configs/phobert.yaml
status: completed

metrics:
  macro_f1: 0.71
  accuracy: 0.74
  val_loss: 0.62
  train_loss: 0.31

per_class:
  fear:
    precision: 0.50
    recall: 0.41
    f1: 0.45
    support: 120
  disgust:
    precision: 0.46
    recall: 0.38
    f1: 0.41
    support: 98

duration_sec: 8640
timestamp: "2026-06-04T10:00:00"

artifacts:
  run_dir: runs/E003
  log_path: runs/E003/train.log
  metrics_path: runs/E003/metrics.json
  report_path: runs/E003/classification_report.json
  config_path: configs/phobert.yaml
```

### 1.5 Index Schema

`.octopus/experiments/index.yaml` should provide quick lookup:

```yaml
latest_id: E003
best_experiment_id: E003
main_metric: macro_f1

experiments:
  - id: E001
    kind: baseline
    name: tfidf_logreg
    main_metric_value: 0.61
    status: completed
  - id: E002
    kind: baseline
    name: tfidf_svc
    main_metric_value: 0.63
    status: completed
  - id: E003
    kind: main
    name: phobert_first_finetune
    main_metric_value: 0.71
    status: completed
```

### 1.6 Memory Markdown Files

Markdown memory is not the source of truth. It is a readable summary generated from structured experiment files.

#### `.octopus/memory/experiments.md`

Should summarize all important runs:

```markdown
# Experiment Memory

## E001 — TF-IDF + Logistic Regression
- Kind: baseline
- Main metric: macro_f1 = 0.61
- Notes: first baseline

## E003 — PhoBERT first fine-tune
- Kind: main
- Main metric: macro_f1 = 0.71
- Delta vs best baseline: +0.08
- Main issue: minority recall remains low
```

#### `.octopus/memory/failures.md`

Should store directions that were tried and did not work:

```markdown
# Failure Memory

## Failed Directions

- E004: increasing epochs from 3 to 8 did not improve macro_f1 and increased val_loss.
- E005: larger batch size made training unstable.

## Avoid Unless New Evidence Appears

- Do not increase epochs before fixing minority recall.
```

#### `.octopus/memory/decisions.md`

Should store user-approved decisions:

```markdown
# Decision Memory

## D1 selected after E003
- Decision: try class weights before changing backbone.
- Reason: target gap is small and minority recall is the bottleneck.
```

---

## 2. Experiment Ingest and Analyze

### 2.1 Purpose

`ingest` imports training evidence into structured experiment memory.

`analyze` diagnoses one experiment using existing state, previous experiments, and task-specific rules.

Keep this deterministic in Phase 2.5.

Do not rely on an LLM to parse raw logs or invent conclusions.

### 2.2 Commands

Implement:

```bash
octopus exp ingest --run-dir runs/E003
octopus exp ingest --metrics runs/E003/metrics.json --report runs/E003/classification_report.json --config configs/phobert.yaml
octopus exp analyze E003
```

Optional convenience alias:

```bash
octopus train review --run-dir runs/E003
```

This alias can run:

```text
exp ingest
exp analyze
exp next
```

but internally keep the steps separate.

### 2.3 Supported Input Artifacts

Priority order:

1. `metrics.json`
2. `classification_report.json`
3. `trainer_state.json`
4. `config.yaml` / `config.yml`
5. `train.log` fallback with regex

Do not start with log regex as the primary source.

Logs are messy and unstable across projects.

### 2.4 Suggested Run Directory Layout

Octopus should handle this layout:

```text
runs/E003/
├── metrics.json
├── classification_report.json
├── trainer_state.json
├── config.yaml
├── train.log
└── checkpoints/
```

Example `metrics.json`:

```json
{
  "macro_f1": 0.71,
  "accuracy": 0.74,
  "val_loss": 0.62,
  "train_loss": 0.31,
  "duration_sec": 8640
}
```

Example `classification_report.json`:

```json
{
  "fear": {
    "precision": 0.50,
    "recall": 0.41,
    "f1-score": 0.45,
    "support": 120
  },
  "disgust": {
    "precision": 0.46,
    "recall": 0.38,
    "f1-score": 0.41,
    "support": 98
  },
  "macro avg": {
    "precision": 0.68,
    "recall": 0.65,
    "f1-score": 0.71,
    "support": 3000
  }
}
```

### 2.5 Ingest Behavior

`octopus exp ingest` should:

1. Validate `.octopus/` exists.
2. Load project state.
3. Read supported artifacts.
4. Extract metrics.
5. Infer or ask for missing fields if needed.
6. Allocate experiment ID.
7. Write `.octopus/experiments/E00X.yaml`.
8. Update `.octopus/experiments/index.yaml`.
9. Print a concise summary.

Example terminal output:

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

### 2.6 Analyze Behavior

`octopus exp analyze E003` should:

1. Load target experiment.
2. Load baseline experiments.
3. Load best previous experiment.
4. Compare main metric.
5. Detect common issues.
6. Write diagnosis into a report.
7. Optionally update experiment YAML with `diagnosis_id`.
8. Update memory markdown summaries.

### 2.7 Diagnosis Rules

Use rule-based diagnosis.

#### Overfitting

Evidence:

```text
train_loss decreases
val_loss increases
main metric stagnates or decreases
```

Diagnosis:

```text
likely_overfitting = true
```

Suggestions:

- early stopping
- dropout/weight decay
- data augmentation
- fewer epochs
- inspect train/validation split

#### Underfitting

Evidence:

```text
train_loss high
val_loss high
main metric low
small gap between train and val
```

Suggestions:

- stronger baseline/model
- better features/preprocessing
- longer training
- learning rate tuning
- inspect input pipeline

#### Class Imbalance / Minority Failure

Evidence:

```text
macro_f1 much lower than accuracy
minority class recall low
per-class support skewed
```

Suggestions:

- class weights
- weighted sampler
- focal loss
- targeted augmentation
- inspect mislabeled minority samples

#### Metric Gap

Evidence:

```text
accuracy high
macro_f1 low
per-class recall uneven
```

Suggestions:

- stop using accuracy-only
- prioritize macro_f1/per-class recall
- inspect confusion matrix

#### Unstable Training

Evidence:

```text
loss spikes
large metric oscillation
NaN/inf in logs
```

Suggestions:

- reduce learning rate
- gradient clipping
- check batch size
- check mixed precision
- inspect data corruption

#### Target Gap

Evidence:

```text
target_score - best_score
```

Rules:

- If gap is small, prefer low-risk fixes.
- If gap is large, consider data/model/pipeline changes.
- If no baseline exists, require baseline first.

### 2.8 Diagnosis Schema

```python
from typing import Literal
from pydantic import BaseModel, Field


class DiagnosisSignal(BaseModel):
    name: str
    status: Literal["detected", "not_detected", "unknown"]
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence: list[str] = Field(default_factory=list)


class ExperimentDiagnosis(BaseModel):
    experiment_id: str
    main_metric: str | None = None
    main_metric_value: float | None = None
    baseline_delta: float | None = None
    best_delta: float | None = None
    target_gap: float | None = None

    signals: list[DiagnosisSignal] = Field(default_factory=list)
    summary: str
    recommended_focus: list[str] = Field(default_factory=list)
```

### 2.9 Training Review Report

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

The report must cite evidence from actual files.

Do not write unsupported claims.

---

## 3. Next-Step Planner

### 3.1 Purpose

`octopus exp next` generates ranked next directions from all experiment history.

It should not produce random generic advice.

It should answer:

- What is the current best run?
- How far are we from target?
- What bottleneck is most likely?
- What has already been tried?
- What should be tried next?
- What should be avoided?
- Which files should Claude Code / Codex read for each direction?
- What commands should be run?
- What is the stop condition?

### 3.2 Command

```bash
octopus exp next
```

Optional flags:

```bash
octopus exp next --top-k 3
octopus exp next --output .octopus/plans/next_steps.md
```

### 3.3 Output

Write:

```text
.octopus/plans/next_steps.md
.octopus/plans/next_steps.yaml
```

Markdown is for humans and coding agents.

YAML is the source of truth for selected directions.

### 3.4 Direction Schema

```python
from typing import Literal
from pydantic import BaseModel, Field


class NextDirection(BaseModel):
    direction_id: str
    title: str
    priority: int
    recommendation: Literal["recommended", "optional", "avoid", "blocked"] = "optional"

    rationale: str
    evidence: list[str] = Field(default_factory=list)

    confidence: Literal["low", "medium", "high"] = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    cost: Literal["low", "medium", "high"] = "medium"
    expected_impact: str | None = None

    files_to_read: list[str] = Field(default_factory=list)
    files_to_edit: list[str] = Field(default_factory=list)
    files_to_avoid: list[str] = Field(default_factory=list)
    commands_to_run: list[str] = Field(default_factory=list)

    guardrails: list[str] = Field(default_factory=list)
    stop_condition: str | None = None
```

### 3.5 Ranking Rules

Use rule-based ranking.

#### If no baseline exists

Top direction:

```text
Create baseline first.
```

Block:

```text
main model training
large backbone
complex ensemble
hyperparameter sweep
```

#### If target gap is small

Prefer:

```text
low-risk fixes
metric-focused improvements
class weights
threshold tuning
minor config changes
```

Avoid:

```text
large architecture change
new dataset pipeline
complex ensemble
```

#### If minority recall is low

Prefer:

```text
class weights
weighted sampler
focal loss
targeted augmentation
minority sample inspection
```

#### If overfitting detected

Prefer:

```text
early stopping
weight decay
dropout
data augmentation
fewer epochs
```

Avoid:

```text
larger model
more epochs
```

#### If underfitting detected

Prefer:

```text
better features
stronger baseline/model
longer training
learning rate tuning
architecture improvement
```

#### If validation unstable

Prefer:

```text
lower learning rate
gradient clipping
smaller batch size
disable unstable mixed precision
inspect bad samples
```

#### If RAG project

Prefer depending on issue:

```text
retrieval recall low → chunking, embedding, BM25/dense hybrid
source hit low → retrieval eval set and citation check
faithfulness low → reranker, source-grounded prompt, answer verifier
latency high → index tuning, caching, smaller embedding model
```

### 3.6 Avoid Recommending Failed Directions

Use `.octopus/memory/failures.md` and experiment tags.

If a direction failed recently, do not recommend it again unless there is new evidence.

Example:

```text
Do not recommend "increase epochs" if the last attempt increased epochs and caused overfitting.
```

### 3.7 `next_steps.md` Template

Required format:

```markdown
# Next Steps — {{ project_name }}

> Generated: {{ generated_at }}  
> Based on: {{ experiment_count }} experiments  
> Current best: {{ best_experiment_id }}  
> Main metric: {{ main_metric }}  
> Target: {{ target_score }}

---

## 1. Current Result

| Experiment | Kind | Model | Main Metric | Delta vs Baseline | Status |
|---|---|---|---:|---:|---|
{% for exp in experiments %}
| {{ exp.id }} | {{ exp.kind }} | {{ exp.model }} | {{ exp.metric }} | {{ exp.delta }} | {{ exp.status }} |
{% endfor %}

## 2. Diagnosis Summary

### Main bottleneck
{{ main_bottleneck }}

### Evidence
{% for item in evidence %}
- {{ item }}
{% endfor %}

### What is unlikely
{% for item in unlikely %}
- {{ item }}
{% endfor %}

## 3. Ranked Directions

{% for direction in directions %}
### {{ direction.direction_id }} — {{ direction.title }}

**Recommendation:** {{ direction.recommendation }}  
**Confidence:** {{ direction.confidence }}  
**Risk:** {{ direction.risk }}  
**Cost:** {{ direction.cost }}  
**Expected impact:** {{ direction.expected_impact }}

**Why this direction:**
{{ direction.rationale }}

**Evidence:**
{% for item in direction.evidence %}
- {{ item }}
{% endfor %}

**Files to read:**
{% for file in direction.files_to_read %}
- `{{ file }}`
{% endfor %}

**Likely files to edit:**
{% for file in direction.files_to_edit %}
- `{{ file }}`
{% endfor %}

**Commands to run:**
```bash
{% for command in direction.commands_to_run %}
{{ command }}
{% endfor %}
```

**Guardrails:**
{% for guardrail in direction.guardrails %}
- {{ guardrail }}
{% endfor %}

**Stop condition:**
{{ direction.stop_condition }}

---
{% endfor %}

## 4. Recommended Choice

Choose {{ recommended_direction_id }} first.

Reason: {{ recommended_reason }}

## 5. Build Agent Context

```bash
octopus exp choose {{ recommended_direction_id }}
octopus context --direction {{ recommended_direction_id }} --target codex
```

## 6. Global Guardrails

- Do not change train/validation/test split unless the selected direction explicitly says so.
- Do not tune on the test set.
- Do not implement multiple directions at once.
- Log the next run with `octopus exp ingest`.
```

---

## 4. Direction-Based Context Builder

### 4.1 Purpose

After the user chooses a direction, Octopus should build a small, targeted context file for Claude Code or Codex.

The agent should not receive every planning file and every code file.

It should receive:

- selected direction
- evidence
- files to read
- likely files to edit
- files to avoid
- commands to run
- guardrails
- definition of done

### 4.2 Commands

```bash
octopus exp choose D1
octopus context --direction D1
octopus context --direction D1 --target codex
octopus context --direction D1 --target claude
```

### 4.3 Selection State

Store selected direction:

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

### 4.4 Context Output

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

### 4.5 File Ranking

Phase 2.5 should use keyword-based file ranking first.

Do not implement embeddings/RAG yet unless the code is already simple.

Example mapping:

```python
DIRECTION_KEYWORDS = {
    "class_imbalance": [
        "loss",
        "class_weight",
        "sampler",
        "weighted",
        "dataset",
        "collate",
        "label",
        "metrics",
    ],
    "augmentation": [
        "augment",
        "preprocess",
        "transform",
        "dataset",
        "tokenizer",
    ],
    "metric": [
        "evaluate",
        "metrics",
        "classification_report",
        "confusion",
        "score",
    ],
    "learning_rate": [
        "optimizer",
        "scheduler",
        "lr",
        "warmup",
        "config",
        "train",
    ],
    "rag_retrieval": [
        "retriever",
        "embedding",
        "chunk",
        "index",
        "vector",
        "bm25",
        "qdrant",
    ],
}
```

### 4.6 Context Safety

Must exclude:

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

### 4.7 Definition of Done

Each context should include a clear completion target.

Example:

```markdown
## Definition of Done

- Implement class weights for the selected training config.
- Do not change dataset split.
- Add or update a test if applicable.
- Run `pytest -q`.
- Run one new training experiment.
- Ingest the result with `octopus exp ingest --run-dir <new_run_dir>`.
```

---

## 5. Runtime Sync for Claude Code and Codex

### 5.1 Purpose

Octopus should update runtime instruction files so Claude Code and Codex use the selected direction and current context correctly.

Existing files:

```text
CLAUDE.md
AGENTS.md
```

Phase 2.5 should make them aware of:

```text
.octopus/context/current_context.md
.octopus/plans/next_steps.md
.octopus/plans/selected_direction.yaml
.octopus/memory/experiments.md
.octopus/memory/failures.md
```

### 5.2 Sync Command

Use existing command if available:

```bash
octopus sync
```

Optionally extend:

```bash
octopus sync --target claude
octopus sync --target codex
octopus sync --training-loop
```

### 5.3 CLAUDE.md Requirements

Generated `CLAUDE.md` should include:

```markdown
## Octopus Training Loop

Before editing training code:

1. Read `.octopus/context/current_context.md`.
2. Read `.octopus/plans/selected_direction.yaml` if it exists.
3. Implement only the selected direction.
4. Do not implement multiple directions at once.
5. Do not change dataset split unless the selected direction explicitly says so.
6. Do not tune on the test set.
7. After a new run, ask the user to run or run:
   `octopus exp ingest --run-dir <run_dir>`
8. Do not edit `.octopus/tasks.json` manually.
9. Do not edit `.octopus/experiments/*.yaml` manually unless the user explicitly asks.
```

### 5.4 AGENTS.md Requirements

Generated `AGENTS.md` should include the same concept, adapted for Codex:

```markdown
## Octopus Instructions for Codex

Before editing ML/DL/RAG training code:

1. Read `.octopus/context/current_context.md`.
2. Follow the selected direction only.
3. Use `.octopus/plans/next_steps.md` as planning background.
4. Use `.octopus/memory/experiments.md` to avoid repeating failed directions.
5. Do not read raw data, checkpoints, secrets, or large logs unless explicitly requested.
6. Do not change validation/test split without an explicit selected direction.
7. Run tests when possible.
8. Keep the patch focused.
```

### 5.5 Sync Safety

`octopus sync` must not silently destroy user edits.

Rules:

- Backup old runtime files before overwrite.
- Or write generated sections between markers.
- Or ask for confirmation unless `--force`.

Recommended marker strategy:

```markdown
<!-- OCTOPUS:BEGIN -->
generated content
<!-- OCTOPUS:END -->
```

Only replace content inside markers.

---

## 6. Hooks and Skills Foundation

### 6.1 Purpose

Hooks and skills are Phase 3-style integrations, but Phase 2.5 should prepare the structure.

Do not build a complex hook runtime yet unless the core experiment workflow is stable.

Phase 2.5 should implement enough structure so future Claude Code / Codex integration is straightforward.

### 6.2 Hooks to Prepare

Future hooks:

```text
post_train
pre_exp_log
post_exp_log
pre_context_build
post_context_build
pre_sync
```

Recommended directory:

```text
.octopus/hooks/
├── post_train.yaml
├── pre_exp_log.yaml
└── post_context_build.yaml
```

Example hook config:

```yaml
event: post_train
enabled: false
command: "octopus exp ingest --run-dir {run_dir} && octopus exp analyze {experiment_id} && octopus exp next"
description: "Automatically ingest and analyze a training run after it finishes."
```

Phase 2.5 behavior:

- Add hook config files only if useful.
- Do not auto-enable destructive hooks.
- Manual commands must remain the default.

### 6.3 Skills to Prepare

Generate optional skill files for Claude Code / Codex later.

Recommended:

```text
.octopus/skills/
├── training-review/
│   └── SKILL.md
├── next-experiment/
│   └── SKILL.md
└── metric-debug/
    └── SKILL.md
```

Example `SKILL.md`:

```markdown
---
name: octopus-training-review
description: Use this skill to review a completed ML training run using Octopus experiment memory.
---

# Octopus Training Review Skill

1. Read `.octopus/context/current_context.md`.
2. Read `.octopus/plans/next_steps.md`.
3. Follow only the selected direction.
4. Do not change train/validation/test split unless explicitly required.
5. Do not tune on test data.
6. After code changes, run tests if possible.
7. Ask the user to run training, then ingest the result with:
   `octopus exp ingest --run-dir <run_dir>`.
```

### 6.4 Export Commands

Optional commands:

```bash
octopus skill list
octopus skill generate training-review
octopus skill export --target claude
octopus skill export --target codex
```

Generated targets could be:

```text
.claude/skills/octopus-training-review/SKILL.md
.codex/skills/octopus-training-review/SKILL.md
```

Only implement export if it is simple and does not destabilize the core workflow.

### 6.5 Future MCP Tool Names

Do not implement full MCP server in Phase 2.5 unless explicitly requested.

But design tool names now:

```text
octopus.get_experiments
octopus.get_best_run
octopus.get_next_steps
octopus.choose_direction
octopus.build_context
octopus.ingest_experiment
octopus.analyze_experiment
```

These names should map cleanly to existing CLI/service functions later.

---

## 7. Implementation Plan

### Step 1 — Schemas

Add or update:

```text
src/octopus/core/schemas.py
```

Add:

- `ExperimentRecord`
- `ExperimentArtifacts`
- `PerClassMetrics`
- `ExperimentDiagnosis`
- `DiagnosisSignal`
- `NextDirection`
- `SelectedDirection`

### Step 2 — Storage

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

### Step 3 — Ingest

Add:

```text
src/octopus/experiments/ingest.py
```

Functions:

```python
ingest_run_dir(run_dir: Path) -> ExperimentRecord
read_metrics_json(path: Path) -> dict[str, float]
read_classification_report(path: Path) -> dict
read_trainer_state(path: Path) -> dict
infer_experiment_metadata(run_dir: Path) -> dict
```

### Step 4 — Analyze

Add:

```text
src/octopus/experiments/analyze.py
```

Functions:

```python
analyze_experiment(experiment_id: str) -> ExperimentDiagnosis
detect_overfitting(record, history) -> DiagnosisSignal
detect_underfitting(record, history) -> DiagnosisSignal
detect_imbalance(record, state) -> DiagnosisSignal
detect_metric_gap(record, state) -> DiagnosisSignal
detect_unstable_training(record, state) -> DiagnosisSignal
```

### Step 5 — Next Planner

Add:

```text
src/octopus/experiments/next_planner.py
```

Functions:

```python
generate_next_directions() -> list[NextDirection]
rank_directions(directions: list[NextDirection]) -> list[NextDirection]
write_next_steps_markdown(directions: list[NextDirection]) -> Path
write_next_steps_yaml(directions: list[NextDirection]) -> Path
```

### Step 6 — Context Direction Support

Update:

```text
src/octopus/context/builder.py
```

Add support for:

```bash
octopus context --direction D1
```

It should load:

```text
.octopus/plans/selected_direction.yaml
.octopus/plans/next_steps.yaml
.octopus/experiments/index.yaml
.octopus/memory/experiments.md
```

### Step 7 — CLI Commands

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

Optional alias:

```bash
octopus train review
octopus train next
octopus train choose
```

### Step 8 — Templates

Add:

```text
src/octopus/templates/training_review.md.j2
src/octopus/templates/next_steps.md.j2
src/octopus/templates/direction_context.md.j2
```

### Step 9 — Runtime Sync

Update templates:

```text
src/octopus/templates/CLAUDE.md.j2
src/octopus/templates/AGENTS.md.j2
```

Add training loop instructions.

### Step 10 — Tests

Add tests:

```text
tests/test_exp_ingest.py
tests/test_exp_analyze.py
tests/test_exp_next.py
tests/test_context_direction.py
tests/test_runtime_sync_training_loop.py
```

Minimum required checks:

- ingest creates `E001.yaml`
- index updates after ingest
- analyze detects low minority recall
- next planner recommends class imbalance direction
- choose writes `selected_direction.yaml`
- context includes selected direction and files to read
- context excludes data/secrets/checkpoints
- CLAUDE.md/AGENTS.md mention current context and selected direction
- main experiment still blocked before baseline
- task progress does not reset after `exp next`

---

## 8. Benchmark Requirements for Phase 2.5

Add benchmark scenarios:

### B1 — Text Classification Minority Recall

Input:

- baseline E001 macro_f1=0.61
- main E003 macro_f1=0.71
- fear recall=0.41
- disgust recall=0.38
- target=0.72

Expected:

- diagnosis detects minority recall issue
- next planner ranks class imbalance direction first
- context includes training/loss/dataset/metrics files
- context does not include raw data

### B2 — Overfitting

Input:

- train_loss decreases
- val_loss increases
- metric stagnates

Expected:

- diagnosis detects overfitting
- next planner recommends early stopping/regularization/augmentation
- does not recommend larger model as first direction

### B3 — No Baseline

Input:

- only main experiment or no experiments

Expected:

- next planner recommends baseline first
- main-model directions are blocked

### B4 — RAG Retrieval

Input:

- retrieval recall low
- faithfulness unknown

Expected:

- next planner recommends retrieval eval/chunking/embedding improvement
- context includes retriever/index/prompt files
- RAG plan requires citation and faithfulness check

### B5 — Secret/Data Safety

Input repo contains:

```text
.env
data/train.csv
checkpoints/model.pt
wandb/
```

Expected:

- context excludes all secret/data/checkpoint content
- report does not print secret values

---

## 9. Non-Goals for Phase 2.5

Do not implement these yet unless explicitly requested:

```text
full autonomous training loop
multi-agent runtime
SQLite database
vector database / embeddings for file ranking
LLM-only diagnosis
automatic remote W&B / MLflow integration
full MCP server
automatic code editing
automatic training rerun without user approval
```

These belong to later phases.

---

## 10. Acceptance Criteria

Phase 2.5 is complete when:

1. `octopus exp ingest --run-dir <run>` creates a valid experiment YAML.
2. `octopus exp analyze <id>` creates a training review report.
3. `octopus exp next` creates `next_steps.md` and `next_steps.yaml`.
4. `octopus exp choose D1` records the selected direction.
5. `octopus context --direction D1` creates a focused agent context.
6. Runtime files tell Claude/Codex to follow selected direction only.
7. Context excludes raw data, checkpoints, logs, and secrets.
8. Tests cover ingest, analyze, next, choose, direction context, and runtime sync.
9. Benchmark includes minority recall, overfitting, no-baseline, RAG, and secret safety scenarios.
10. No LLM is required for the core workflow.

---

## 11. Design Rule

The most important design rule:

```text
Markdown is the view. YAML/JSON is the source of truth.
```

Do not make `next_steps.md` or `training_review.md` the only source of truth.

Store structured data in YAML/JSON, then render markdown from it.

This keeps Octopus reliable for future hooks, skills, MCP tools, and agents.
