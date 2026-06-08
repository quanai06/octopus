# Getting Started

A complete first run: from an empty folder to a logged baseline and a ranked next
direction. This tutorial uses a text-classification example but the flow is the
same for DL and RAG.

## 1. Install

```bash
git clone <this-repo-url>
cd octopus
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
octopus --help        # verify
```

Python 3.11+ is required.

## 2. Create a project

```bash
mkdir viet-emotion-classifier && cd viet-emotion-classifier
octopus init --runtime claude,codex
```

This creates `.octopus/` plus empty planning files.

## 3. Capture requirements

Interactive:

```bash
octopus ask
```

Or headless (no prompts) — write `answers.yaml` and run:

```bash
octopus ask --from answers.yaml
```

See [Headless setup](guides/headless-setup.md) for the `answers.yaml` format.

## 4. Render the plan

```bash
octopus plan        # requirements.md
octopus ml-plan     # ml_design.md, experiment_plan.md, data_strategy.md, compute_budget.md
octopus tasks       # tasks.md + .octopus/tasks.json
```

## 5. Build the working context

```bash
octopus task next                                          # first unblocked task
octopus context --task "train the baseline" --profile training
```

Your agent reads only `.octopus/context/current_context.md` — a compact,
task-focused file instead of every planning doc.

## 6. Run and log the baseline

Train your baseline however you like, then record it:

```bash
octopus exp ingest --run-dir runs/baseline --kind baseline   # auto-detects MLflow/W&B/TB
# or, without artifacts:
octopus exp log --kind baseline --name baseline --metric macro_f1=0.58
```

Logging a completed baseline marks `T010`/`T011`/`T012` done and unblocks `T020`.

## 7. Understand the baseline, then improve

```bash
octopus exp profile        # .octopus/reports/baseline_profile.md
octopus exp next           # ranked directions -> .octopus/plans/next_steps.md
octopus exp choose D1      # select one
octopus context --direction D1 --target claude
```

Implement only that one direction, ingest the new run, and re-profile. That loop
— one controlled change per experiment — is the whole point.

## What you end up with

```text
requirements.md  ml_design.md  experiment_plan.md  data_strategy.md
compute_budget.md  tasks.md  CLAUDE.md  AGENTS.md
.octopus/
  config.yaml  project_state.json  tasks.json
  context/current_context.md
  experiments/  reports/  plans/  memory/  session/  adr/
```

Next: read [Concepts](concepts.md) to understand why the flow is shaped this way.
