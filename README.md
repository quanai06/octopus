# CLI Octopus

[![CI](https://github.com/quanai06/octopus/actions/workflows/ci.yml/badge.svg)](https://github.com/quanai06/octopus/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cli-octopus.svg)](https://pypi.org/project/cli-octopus/)

Octopus is a Python CLI that turns an ML/DL/RAG project into a baseline-first
workflow for Codex. It captures project requirements, renders planning files,
builds a compact task context, tracks experiments, and keeps Codex from jumping
straight to the main model before a real baseline exists.

The intended Codex loop is:

```text
requirements -> plan -> baseline context -> baseline run -> ingest/profile
-> selected next direction -> one controlled improvement
```

Octopus is not a training framework. It is the project brain and guardrail layer
around your training/eval scripts.

📚 **Full documentation:** [`docs/`](docs/README.md) — getting started, concepts,
how-to guides (Claude Code, Codex, headless, tracker ingest, tuning loop, resume),
and a complete CLI / configuration / files reference.

## What Octopus Gives Codex

- A one-command baseline setup prompt: `octopus-baseline`.
- A compact working file: `.octopus/context/current_context.md`.
- Baseline-first task gates in `.octopus/tasks.json`.
- Experiment memory in `.octopus/experiments/`.
- Baseline profiling and next-step selection.
- Codex prompt routers installed under `~/.codex/prompts/`.

Official Codex references:

- Codex docs: https://developers.openai.com/codex
- Codex CLI docs: https://developers.openai.com/codex/cli
- Codex use cases: https://developers.openai.com/codex/use-cases

## Install

Install the released package from PyPI:

```bash
python -m pip install cli-octopus
octopus --help
```

Python 3.11+ is required.

Install the latest GitHub version without waiting for a PyPI release:

```bash
python -m pip install git+https://github.com/quanai06/octopus.git
```

For local development:

```bash
git clone https://github.com/quanai06/octopus.git
cd octopus

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the dev install:

```bash
octopus --help
pytest
```

Install Codex CLI if you do not already have it:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex
```

Then install Octopus' Codex prompt routers once:

```bash
octopus install --runtime codex
```

This writes:

```text
~/.codex/prompts/octopus-baseline.md
~/.codex/prompts/octopus-plan.md
~/.codex/prompts/octopus-train.md
~/.codex/prompts/octopus-tune.md
~/.codex/prompts/octopus-status.md
~/.codex/prompts/octopus-resume.md
~/.codex/.octopus-manifest.json
```

Uninstall:

```bash
octopus uninstall --runtime codex
```

## Fast Start With Codex

One-time machine setup:

```bash
python -m pip install cli-octopus
octopus install --runtime codex
```

Per ML/DL/RAG project:

```bash
cd your-ml-project
codex
```

In Codex, type:

```text
octopus-baseline
```

That one prompt router is the normal path. It tells Codex to initialize Octopus
if needed, collect missing project facts, render the plan/tasks/context, read
`.octopus/context/current_context.md`, write the baseline plan plus script
skeleton, and stop before training. The manual commands below are only for
debugging or full control.

Expected behavior:

1. If `.octopus/` is missing, Codex runs `octopus init --runtime claude,codex`.
2. Codex collects or writes missing project facts.
3. Codex runs `octopus ask --from answers.yaml` when it can avoid an interactive TTY.
4. Codex runs `octopus plan`, `octopus ml-plan`, and `octopus tasks`.
5. Codex runs `octopus task next`.
6. Codex runs `octopus context --task "train the baseline" --profile training`.
7. Codex reads `.octopus/context/current_context.md`.
8. Codex writes the baseline plan and baseline script skeleton.
9. Codex stops before training unless you explicitly ask it to run the baseline.

If your Codex surface does not expand prompt files by name, open or paste:

```bash
cat ~/.codex/prompts/octopus-baseline.md
```

Then paste that content into Codex.

## Manual Codex Setup

Use this when you want full control instead of the one-shot `octopus-baseline`
router.

```bash
mkdir viet-emotion-classifier
cd viet-emotion-classifier

octopus init --runtime codex
octopus ask
octopus plan
octopus ml-plan
octopus tasks
octopus task next
octopus context --task "train the baseline" --profile training
codex
```

Prompt Codex:

```text
This project uses Octopus. Run `octopus task next`, then read ONLY
`.octopus/context/current_context.md` as your working context.

Implement the baseline first and stop after writing the baseline training-script
skeleton. Do not train unless I explicitly ask. Do not start the main model
before a baseline, do not change the train/validation/test split, and do not tune
on the test set.
```

## Headless Setup For Codex

`octopus ask` is interactive. For Codex, CI, or benchmark runs, use a YAML/JSON
answers file.

Example `answers.yaml`:

```yaml
project_name: VSMEC Emotion Classifier
project_goal: Build a Vietnamese social-media emotion classifier.
target_users: ML engineers
project_type: machine learning
task_type: text_classification
input_type: text
output_type: emotion_label
dataset_status: available
dataset_size_note: tests/datasets/vsmec, fixed train/valid/test XLSX files
has_labels: true
has_class_imbalance: true
main_metric: macro_f1
baseline_model: TF-IDF + Logistic Regression
runtime:
  - codex
compute:
  has_gpu: false
  budget_note: CPU only
```

Run:

```bash
octopus init --runtime codex --force
octopus ask --from answers.yaml
octopus plan
octopus ml-plan
octopus tasks
octopus context --task "train the baseline" --profile training
```

Then ask Codex to read only:

```text
.octopus/context/current_context.md
```

## Use With Claude Code

Octopus installs the same baseline-first workflow into Claude Code, plus two
things the Codex surface does not get: specialized subagents and a hard
`PreToolUse` guard.

Install the Claude Code artifacts:

```bash
octopus install --runtime claude
```

This writes:

```text
~/.claude/commands/octopus-baseline.md
~/.claude/commands/octopus-plan.md
~/.claude/commands/octopus-train.md
~/.claude/commands/octopus-tune.md
~/.claude/commands/octopus-status.md
~/.claude/commands/octopus-resume.md
~/.claude/agents/octopus-baseline-runner.md
~/.claude/agents/octopus-experiment-analyst.md
~/.claude/agents/octopus-tuner.md
~/.claude/agents/octopus-data-auditor.md
~/.claude/agents/octopus-rag-evaluator.md
~/.claude/settings.json            # baseline-guard PreToolUse hook (merged, idempotent)
~/.claude/.octopus-manifest.json
```

Existing `settings.json` keys are preserved, and reinstalling never duplicates
the hook.

### Fast start

From inside your ML/DL/RAG project:

```bash
octopus install --runtime claude
claude
```

In Claude Code, run the slash command:

```text
/octopus-baseline
```

It follows the same path as Codex: initialize if needed, collect missing facts
and run `octopus ask --from answers.yaml`, then `octopus plan --force`,
`octopus ml-plan --force`, `octopus tasks --force`, `octopus task next`,
`octopus context --task "train the baseline" --profile training`, read
`.octopus/context/current_context.md`, write the baseline plan + script skeleton,
and stop before training.

Other slash commands: `/octopus-plan`, `/octopus-train`, `/octopus-tune`,
`/octopus-status`, `/octopus-resume`.

### Subagents

Claude Code can delegate to the installed subagents:

- `octopus-baseline-runner` — establish and ingest the first baseline.
- `octopus-experiment-analyst` — analyze/profile a finished run.
- `octopus-tuner` — implement exactly one selected direction.
- `octopus-data-auditor` — split / leakage / imbalance audit.
- `octopus-rag-evaluator` — retrieval eval + citation/faithfulness.

### Baseline-guard hook

A `PreToolUse` hook on the Bash tool blocks main-model training before a
completed baseline exists. Commands like `python train.py`,
`accelerate launch train.py`, `torchrun ...`, `python train_phobert.py`, or any
`fine-tune` command exit with code `2` and an explanation until you log a
baseline. The baseline scripts themselves are not blocked.

### Manual setup

Use this for full control instead of the one-shot `/octopus-baseline`:

```bash
octopus init --runtime claude
octopus ask                     # or: octopus ask --from answers.yaml  (headless)
octopus plan
octopus ml-plan
octopus tasks
octopus task next
octopus context --task "train the baseline" --profile training
claude
```

Then prompt Claude Code:

```text
This project uses Octopus. Run `octopus task next`, then read ONLY
`.octopus/context/current_context.md` as your working context.

Implement the baseline first and stop after writing the baseline training-script
skeleton. Do not train unless I ask. Do not start the main model before a
baseline, do not change the train/validation/test split, and do not tune on the
test set.
```

Uninstall:

```bash
octopus uninstall --runtime claude
```

Install both runtimes at once with `octopus install --runtime claude,codex`.

## Commands

Core project setup:

```bash
octopus init      # create .octopus/ plus generated files
octopus ask       # interactive intake, or --from answers.yaml
octopus plan      # render requirements.md
octopus ml-plan   # render ml_design/data/compute/experiment plans
octopus tasks     # render tasks.md and .octopus/tasks.json
octopus sync      # refresh AGENTS.md / CLAUDE.md from current state
octopus status    # show project snapshot
```

Task/context commands:

```bash
octopus task next
octopus task start T010
octopus task done T010
octopus context --task "train the baseline" --profile training
octopus context --direction D1 --target codex
```

Experiment commands:

```bash
octopus exp log --kind baseline --name baseline --metric macro_f1=0.58
octopus exp ingest --run-dir <run_dir> --kind baseline
octopus exp profile
octopus exp next
octopus exp choose D1
octopus exp compare --metric macro_f1
octopus exp report
```

Structured tools and MCP:

```bash
octopus status --json
octopus task next --json
octopus context --task "train the baseline" --profile training --json
octopus exp ingest --run-dir <run_dir> --kind baseline --json
octopus exp profile --json

octopus tool list --json
octopus tool call octopus_status
octopus tool call octopus_build_context --input-json '{"task":"train baseline"}'

octopus mcp   # MCP stdio server
```

The structured tools expose JSON schemas for function-calling style agents:
`octopus_status`, `octopus_task_next`, `octopus_build_context`,
`octopus_ingest_run`, and `octopus_profile_baseline`. The MCP server exposes the
same tools plus resources such as `octopus://context/current`,
`octopus://memory/experiments`, `octopus://session/current`, and
`octopus://reports/baseline_profile`.

Runtime install:

```bash
octopus install --runtime codex
octopus uninstall --runtime codex
```

## Generated Files

Project files:

```text
requirements.md
ml_design.md
experiment_plan.md
data_strategy.md
compute_budget.md
tasks.md
AGENTS.md
```

Octopus state:

```text
.octopus/config.yaml
.octopus/project_state.json
.octopus/tasks.json
.octopus/context/current_context.md
.octopus/experiments/
.octopus/reports/
.octopus/plans/
.octopus/session/
.octopus/memory/
```

Codex prompt routers:

```text
~/.codex/prompts/octopus-baseline.md
~/.codex/prompts/octopus-plan.md
~/.codex/prompts/octopus-train.md
~/.codex/prompts/octopus-tune.md
~/.codex/prompts/octopus-status.md
~/.codex/prompts/octopus-resume.md
```

## Baseline-First Rules

For ML/DL/RAG projects, Octopus enforces these rules:

- Start with a simple reproducible baseline.
- Do not log or start main-model work before a completed baseline exists.
- Do not tune on the test set.
- Do not change train/validation/test split unless the selected direction says so.
- Change one thing per experiment.
- Track the project's main metric and diagnostic metrics, not just accuracy.

Logging or ingesting a completed baseline marks `T010`, `T011`, and `T012` done,
then unblocks `T020`.

### What "baseline" means here

The baseline is a **full, data-type-aware train/eval protocol** — not a single
random split. `octopus ml-plan` renders a "Split & Cross-Validation" section in
`data_strategy.md` and `experiment_plan.md`, chosen by task type:

| Task | Split + CV |
|---|---|
| text / image classification | canonical cleaned dataset manifest; StratifiedKFold(k=5) + per-class recall, mean ± std; StratifiedGroupKFold if rows share a group; for deep models use k-fold when feasible or ≥3 fixed seeds with an explicit exception |
| regression (tabular) | KFold(k=5); GroupKFold if rows share an entity; TimeSeriesSplit if the target is time-ordered |
| forecasting | TimeSeriesSplit (expanding/rolling), never shuffle, lag features computed inside each fold, compared to a naive baseline |
| retrieval / RAG | canonical cleaned corpus manifest; fixed labeled query eval set; documented chunking grid; fixed top-k grid; Recall@k / MRR / source-hit; rerank only later over a recorded candidate pool; never tune on test queries |
| recommendation | time-aware split on future interactions; guard cold-start and leakage |
| other | default: held-out test + k-fold (fold scheme chosen to match the data) |

Across all of them: preprocessing is fit **inside each fold** (leakage-safe), the
held-out test set stays untouched until final reporting, and the main metric is
reported as **mean ± std across folds**. The model can be simple; the *protocol*
is rigorous.

Example:

```bash
octopus exp ingest --run-dir runs/E001 --kind baseline
octopus exp profile
octopus exp next
octopus exp choose D1
octopus context --direction D1 --target codex
```

Then in Codex:

```text
Read `.octopus/context/current_context.md` and implement only selected direction D1.
Do not implement multiple directions at once. Stop before training unless I ask.
```

## Baseline Profile And Tuning

After a baseline is logged:

```bash
octopus exp profile
```

Octopus writes:

```text
.octopus/reports/baseline_profile.md
```

The profile reports:

- baseline standing vs target;
- weak classes or low retrieval metrics;
- bias/variance symptoms;
- data quality flags;
- recommended techniques;
- "Do Not Try Yet" items.

Then:

```bash
octopus exp next
octopus exp choose D1
octopus context --direction D1 --target codex
```

This gives Codex a smaller direction-specific context instead of the whole
planning history.

## Tracker Auto-Ingest

`octopus exp ingest` can read common tracker output directories:

```bash
octopus exp ingest --run-dir mlruns/0/<run_id> --kind baseline   # MLflow
octopus exp ingest --run-dir wandb/run-<id>                      # W&B
octopus exp ingest --run-dir runs/<name>                         # TensorBoard
octopus exp ingest --run-dir runs/E001 --tracker none            # plain files
```

Plain run directories can include:

```text
metrics.json
classification_report.json
config.yaml
```

## Session Resume

Use this when Codex loses context or starts a new session:

```bash
octopus session start --goal "beat the baseline"
octopus session show
octopus resume
```

Then in Codex:

```text
octopus-resume
```

or paste:

```bash
cat ~/.codex/prompts/octopus-resume.md
```

## Benchmarks

Benchmarks are deterministic local token measurements using Octopus'
`cl100k_base` estimator. They do not train models.

### Baseline Plan + Script Skeleton

```bash
python tests/benchmark/token_eval_datasets.py
```

Datasets:

| Scenario | Dataset | Task |
|---|---|---|
| ML | `tests/datasets/vsmec` | Vietnamese emotion classification |
| DL | `tests/datasets/alpaca-dataset/dataset` | Alpaca / not-alpaca image classification |
| RAG | `tests/datasets/wikiqa` | BM25 retrieval evaluation |

Latest local result:

| Scenario | A prompt-only input | B Octopus input | Saving | Output plan+script |
|---|---:|---:|---:|---:|
| ML | 3,733 | 2,750 | 26.3% | 708 |
| DL | 2,437 | 2,027 | 16.8% | 397 |
| RAG | 2,512 | 2,027 | 19.3% | 432 |

### Post-Baseline Stacking / Fusion Upgrade

```bash
python tests/benchmark/token_eval_post_baseline.py
```

Latest local result:

| Scenario | A prompt-only input | B Octopus direction input | Saving | Output plan+script |
|---|---:|---:|---:|---:|
| ML | 5,001 | 1,222 | 75.6% | 270 |
| DL | 3,531 | 1,214 | 65.6% | 274 |
| RAG | 3,611 | 1,196 | 66.9% | 271 |

Interpretation:

- First baseline turn saves moderately because Codex still needs project facts.
- Post-baseline tuning saves much more because Octopus compresses state into a
  selected direction, evidence, guardrails, and relevant code context.

Agent-dependent live token usage is separate. Measure it from Codex' own usage
counter in fresh sessions and score the produced artifacts with the rubric in:

```text
eval_token_and_compliance.md
```

## Troubleshooting

`octopus` command not found:

```bash
source .venv/bin/activate
python -m pip install cli-octopus
octopus --help
```

For a local checkout:

```bash
python -m pip install -e ".[dev]"
python -m octopus.cli.main --help
```

Codex does not recognize `octopus-baseline`:

```bash
octopus install --runtime codex
ls ~/.codex/prompts
cat ~/.codex/prompts/octopus-baseline.md
```

Then paste the prompt content into Codex.

Codex tries to skip the baseline:

```text
Read `.octopus/context/current_context.md`. Follow Octopus baseline-first rules.
Do not start the main model before a completed baseline exists.
```

No baseline exists but you want to tune:

```bash
octopus task next
octopus context --task "train the baseline" --profile training
```

After the real baseline run:

```bash
octopus exp ingest --run-dir <run_dir> --kind baseline
octopus exp profile
```

## CI/CD

GitHub Actions workflows live in `.github/workflows/`.

CI runs on push to `main`, pull requests to `main`, and manual dispatch:

```text
.github/workflows/ci.yml
```

CI jobs:

- Python 3.11 and 3.12 run the same local gate as developers:

```bash
make check
```

- A package build job verifies source distribution and wheel creation:

```bash
python -m build
```

Publishing is release-driven:

```text
.github/workflows/publish.yml
```

It builds the package and publishes to PyPI when a GitHub Release is published.
The workflow uses PyPI Trusted Publishing (`id-token: write`), so configure the
PyPI project to trust:

```text
owner: quanai06
repository: octopus
workflow: publish.yml
environment: pypi
```

Release flow:

```bash
make check
python -m build
git tag v0.1.1
git push origin v0.1.1
```

Then create/publish the GitHub Release for that tag. The publish workflow will
upload the package to PyPI.

PyPI never allows re-uploading the same version. If the workflow fails with
`File already exists`, that version is already published. Bump `pyproject.toml`
to the next unused version:

```toml
version = "0.1.2"
```

then commit, tag, and publish a new GitHub Release.

After publish, test the package from a clean environment:

```bash
python -m venv /tmp/octopus-test
source /tmp/octopus-test/bin/activate
python -m pip install cli-octopus
octopus --help
octopus tool list --json
```

## License

MIT. See [LICENSE](LICENSE).

## Development

```bash
python tests/benchmark/token_eval_datasets.py
python tests/benchmark/token_eval_post_baseline.py
pytest
ruff check .
mypy src
```

This README is Codex-first, but Claude Code is fully supported — see
[Use With Claude Code](#use-with-claude-code) for slash commands, subagents, and
the baseline-guard hook.
