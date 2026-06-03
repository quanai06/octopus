# CLI Octopus

Octopus is a Python CLI for ML/DL project planning. It captures project requirements,
generates planning files, builds a compact working context for Claude Code or Codex,
and blocks model work until the project has an explicit plan.

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
octopus context   # build smart .octopus/context/current_context.md
octopus exp       # init, log, compare, diagnose, suggest, and report experiments
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
octopus context --task "train TF-IDF baseline" --profile training --budget 6000
octopus exp log --name tfidf_baseline --metric macro_f1=0.58 --note "stable baseline"
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
instead of always loading every planning file in full. Supported profiles are
`planning`, `training`, `debugging`, and `review`.

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

## Development

```bash
pytest
ruff check .
mypy src
```
