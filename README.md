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
octopus ml-plan   # render ml_design.md and experiment_plan.md
octopus tasks     # render tasks.md
octopus context   # build .octopus/context/current_context.md
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
octopus context --task "train TF-IDF baseline"
octopus sync
octopus status
```

Expected files:

```text
requirements.md
ml_design.md
experiment_plan.md
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

Phase 1 includes the full contents of generated plan files in the context file and
estimates token count with `tiktoken`. It excludes common heavy or irrelevant files,
including `.venv/`, `.git/`, `data/`, `datasets/`, checkpoints, model weights, CSVs,
Parquet files, logs, `wandb/`, and `mlruns/`. Additional patterns from `.gitignore`
are respected.

## Development

```bash
pytest
ruff check .
mypy src
```
