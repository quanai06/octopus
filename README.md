# CLI Octopus

Octopus is a Python CLI for ML/DL project planning. It captures project requirements,
generates planning files, builds a compact working context for Claude Code or Codex,
and blocks model work until the project has an explicit plan.

For ML/DL/RAG projects, Octopus asks the user to choose the baseline model from
task-specific options instead of typing the baseline manually. That selected baseline
is then used by `ml_design.md`, `experiment_plan.md`, `.octopus/tasks.json`, and
baseline-first enforcement.

Every single-choice or multi-choice intake prompt keeps a `custom...` option at the end,
so users can pick a suggested workflow value or write their own when the defaults do not fit.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11+ is required.

## Commands

```bash
octopus init      # create .octopus/ plus planning files
octopus ask       # interactive requirement intake
octopus plan      # render requirements.md
octopus ml-plan   # render ML design, data, compute, and experiment plans
octopus tasks     # render tasks.md
octopus task      # manage real task state and dependency gates
octopus context   # build smart .octopus/context/current_context.md
octopus exp       # init, log, ingest, analyze, profile, next, compare, and report experiments
octopus sync      # refresh CLAUDE.md and/or AGENTS.md
octopus status    # show project snapshot
```

`octopus --help` lists the full Phase 1 command surface.

## Demo Flow

```bash
mkdir viet-emotion-classifier
cd viet-emotion-classifier

octopus init --runtime claude,codex
octopus ask
octopus plan
octopus ml-plan
octopus tasks
octopus task next
octopus task start T010
octopus context --task "train TF-IDF baseline" --profile training --budget 6000
octopus exp log --kind baseline --name tfidf_baseline --metric macro_f1=0.58 --note "stable baseline"
octopus task start T020
octopus sync
octopus status
```

Expected files:

```text
requirements.md
ml_design.md
experiment_plan.md
data_strategy.md
compute_budget.md
tasks.md
.octopus/tasks.json
CLAUDE.md
AGENTS.md
.octopus/config.yaml
.octopus/project_state.json
.octopus/context/current_context.md
.octopus/experiments/
.octopus/adr/
```

## Context Rules

`octopus context` builds a task-focused context file from selected markdown sections
and relevant code snippets instead of always loading every planning file in full.
Supported profiles are `planning`, `training`, `debugging`, and `review`.

```bash
octopus context --task "train PhoBERT baseline" --profile training
octopus context --task "debug low macro F1" --profile debugging --budget 4000
octopus context --task "review experiment plan" --profile review
octopus context --task "inspect all planning docs" --full
```

The context builder estimates token count with `tiktoken`. It excludes common heavy
or irrelevant files, including `.venv/`, `.git/`, `data/`, `datasets/`, checkpoints,
model weights, CSVs, Parquet files, logs, `wandb/`, and `mlruns/`. Additional patterns
from `.gitignore` are respected.

## ML Planner

`octopus ml-plan` generates ML-specific planning artifacts:

```text
ml_design.md
experiment_plan.md
data_strategy.md
compute_budget.md
```

For ML/DL tasks it frames the problem type, baseline models, candidate models,
metrics, dataset checks, compute limits, first experiments, and stop conditions before
training starts.

## Experiment Memory

`octopus exp` stores simple experiment memory in `.octopus/experiments/`.

```bash
octopus exp init

octopus exp log \
  --kind baseline \
  --name phobert_weighted_loss \
  --model phobert-base \
  --dataset vietnamese_emotion \
  --metric macro_f1=0.72 \
  --metric fear_recall=0.51 \
  --note "Improved minority recall but overfit after epoch 3"

octopus exp list
octopus exp compare --metric macro_f1
octopus exp diagnose --exp exp_001
octopus exp suggest
octopus exp report
```

For ML/DL/RAG projects, Octopus blocks main-model experiment logging until a completed
baseline exists. Logging a completed baseline marks `T010`, `T011`, and `T012` done
in `.octopus/tasks.json`, which unblocks `T020`.

Each run is saved as YAML and indexed locally:

```text
.octopus/
  experiments/
    index.yaml
    exp_001.yaml
  reports/
    experiment_report.md
```

Experiment diagnosis and suggestions are rule-based. Octopus flags overfitting,
underfitting, high accuracy with low macro F1, low minority recall, weak overall
metrics, unstable loss, and metrics that stop changing across recent runs.

## Baseline Profile

Before tuning, `octopus exp profile` builds a deep understanding of the baseline
and writes `.octopus/reports/baseline_profile.md`:

```bash
octopus exp profile            # profile the best completed baseline
octopus exp profile --exp E001 # profile a specific run
octopus exp profile --top-k 3  # limit recommended techniques
```

The profile reports where the baseline stands vs the target, whether it is
bias- or variance-limited, weak classes, data-quality risks, and a ranked list
of concrete tuning techniques (plus a "Do Not Try Yet" list). Recommendations
are domain-aware: classification, regression, and RAG/retrieval each draw from a
deterministic technique library (`octopus.experiments.technique_library`) that
maps diagnosed symptoms to techniques, ordered by leverage, cost, and risk.

## Tracker Auto-Ingest

`octopus exp ingest` auto-detects and reads common experiment trackers, so you
can point it at a tracker run directory instead of writing `metrics.json` by hand:

```bash
octopus exp ingest --run-dir mlruns/0/<run_id> --kind baseline   # MLflow
octopus exp ingest --run-dir wandb/run-<id>                       # Weights & Biases
octopus exp ingest --run-dir runs/<name>                          # TensorBoard
octopus exp ingest --run-dir runs/E001 --tracker none            # disable detection
```

MLflow and W&B are parsed directly from their on-disk files (no extra
dependency). TensorBoard event files need the optional `tensorboard` package;
without it, ingest reports a clear install hint. Detected runs are tagged with
their source (for example `source:mlflow`). Explicit `--metrics` / `--report`
files always take precedence over tracker values.

## Development

```bash
pytest
ruff check .
mypy src
```
