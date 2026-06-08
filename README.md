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

Install Octopus from this repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11+ is required.

Install an agent runtime if you want Octopus to steer Codex or Claude Code:

```bash
# Codex CLI, macOS/Linux
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# Claude Code, macOS/Linux/WSL
curl -fsSL https://claude.ai/install.sh | bash
```

Then authenticate by running the runtime once:

```bash
codex
claude
```

References:
- Codex CLI docs: https://developers.openai.com/codex/cli
- Claude Code setup docs: https://code.claude.com/docs/en/getting-started

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
octopus session   # short-term in-session memory (start, show, log, end)
octopus resume    # restore working context after a reset
octopus install   # embed Octopus commands/agents/hook into Claude Code & Codex
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

## Use With Codex

Install Octopus prompt routers into Codex:

```bash
octopus install --runtime codex
```

This writes managed markdown prompts under `~/.codex/prompts/`:

```text
octopus-plan.md
octopus-train.md
octopus-tune.md
octopus-status.md
octopus-resume.md
```

Recommended Codex loop:

```bash
octopus init --runtime codex
octopus ask
octopus plan
octopus ml-plan
octopus tasks
octopus task next
octopus context --task "train the baseline" --profile training
codex
```

Prompt Codex with the installed router or the equivalent text:

```text
This project uses Octopus. Run `octopus task next`, then read ONLY
`.octopus/context/current_context.md` as your working context. Implement the
baseline first. Do not start the main model before a baseline, do not change
the train/validation/test split, and do not tune on the test set.
```

After a real training run, ingest it and profile the baseline before tuning:

```bash
octopus exp ingest --run-dir <run_dir> --kind baseline
octopus exp profile
octopus exp next
octopus exp choose D1
octopus context --direction D1 --target codex
```

## Use With Claude Code

Install Octopus commands, subagents, and the baseline guard hook into Claude Code:

```bash
octopus install --runtime claude
```

This writes managed files under `~/.claude/`:

```text
commands/octopus-plan.md
commands/octopus-train.md
commands/octopus-tune.md
commands/octopus-status.md
commands/octopus-resume.md
agents/octopus-baseline-runner.md
agents/octopus-experiment-analyst.md
agents/octopus-tuner.md
agents/octopus-data-auditor.md
agents/octopus-rag-evaluator.md
settings.json  # merged PreToolUse baseline-guard hook
```

Recommended Claude Code loop:

```bash
octopus init --runtime claude
octopus ask
octopus plan
octopus ml-plan
octopus tasks
octopus context --task "train the baseline" --profile training
claude
```

Inside Claude Code, use the installed slash commands:

```text
/octopus-plan
/octopus-train
/octopus-tune
/octopus-status
/octopus-resume
```

The Claude `PreToolUse` baseline guard blocks shell commands that look like
main-model training before a completed baseline exists. When it blocks, it exits
with code `2` and tells the agent to log or ingest a baseline first.

To remove installed runtime artifacts:

```bash
octopus uninstall --runtime claude,codex
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

## Runtime Integration (Claude Code & Codex)

`octopus install` embeds Octopus into your AI runtimes so you are steered into the
baseline-first workflow with a small token surface:

```bash
octopus install --runtime claude,codex     # install into ~/.claude and ~/.codex
octopus install --runtime claude --home /tmp/sandbox   # install into a custom base
octopus uninstall --runtime claude,codex   # clean removal (manifest-driven)
```

It writes thin command routers (`/octopus-plan`, `/octopus-train`, `/octopus-tune`,
`/octopus-status`, `/octopus-resume`), Claude subagents
(`octopus-baseline-runner`, `octopus-experiment-analyst`, `octopus-tuner`,
`octopus-data-auditor`, `octopus-rag-evaluator`), and a Claude `PreToolUse`
**baseline-guard** hook that blocks main-model training before a baseline exists.
Existing `settings.json` is preserved; the hook is idempotent.

## Session Memory

`octopus session` keeps short-term, in-session memory in `.octopus/session/` so a
runtime can be restored after a context reset. It auto-captures from the workflow
(`task start`, `exp choose`, `exp ingest`):

```bash
octopus session start --goal "beat the TF-IDF baseline"
octopus session show
octopus resume          # summary + which restore files exist
octopus session end
```

This is distinct from `.octopus/memory/` (long-term experiment archive): the
session is RAM, memory is history.

## Benchmarks

Benchmarks are deterministic local token measurements. They use Octopus'
`cl100k_base` token estimator and stop at a fixed deliverable. They do not train
models. Live Codex/Claude Code token usage should still be measured separately
with fresh sessions if you want runtime billing/compliance numbers.

### Benchmark 1: Baseline Plan + Script Skeleton

Command:

```bash
python tests/benchmark/token_eval_datasets.py
```

Datasets:

| Scenario | Dataset | Task |
|---|---|---|
| ML | `tests/datasets/vsmec` | Vietnamese emotion classification |
| DL | `tests/datasets/alpaca-dataset/dataset` | Alpaca / not-alpaca image classification |
| RAG | `tests/datasets/wikiqa` | BM25 retrieval evaluation |

Measurement:

- Branch A = detailed prompt + dataset summary + six planning docs.
- Branch B = Octopus prompt + `.octopus/context/current_context.md`.
- Output = deterministic `baseline_plan.md` + `baseline_script_skeleton.py`.

Latest local result:

| Scenario | A prompt-only input | B Octopus input | Saving | Output plan+script |
|---|---:|---:|---:|---:|
| ML | 3,733 | 2,750 | 26.3% | 708 |
| DL | 2,437 | 2,027 | 16.8% | 397 |
| RAG | 2,512 | 2,027 | 19.3% | 432 |

Interpretation: the first baseline turn saves a moderate amount because Octopus
still has to carry project facts, dataset facts, metrics, split rules, and
baseline-first constraints.

### Benchmark 2: Post-Baseline Stacking / Fusion Upgrade

Command:

```bash
python tests/benchmark/token_eval_post_baseline.py
```

Setup:

- Create a temporary Octopus project for each scenario.
- Log a completed baseline `E001`.
- Generate a baseline profile.
- Choose a post-baseline direction:
  - ML/DL: leakage-safe stacking with out-of-fold predictions.
  - RAG: lexical retriever stack with reciprocal-rank fusion.
- Build `octopus context --direction D1 --target codex`.
- Stop after `upgrade_plan.md` + `stacking_script_skeleton.py`; no training.

Measurement:

- Branch A = prompt-only grounding with prompt, dataset summary, planning docs,
  baseline profile, next-step docs, and relevant code snippets.
- Branch B = Octopus prompt + selected direction context.

Latest local result:

| Scenario | A prompt-only input | B Octopus direction input | Saving | Output plan+script |
|---|---:|---:|---:|---:|
| ML | 5,001 | 1,222 | 75.6% | 270 |
| DL | 3,531 | 1,214 | 65.6% | 274 |
| RAG | 3,611 | 1,196 | 66.9% | 271 |

Interpretation: after the baseline, Octopus saves much more context because the
state is compressed into selected direction, evidence, guardrails, and relevant
code. Prompt-only has to paste the same grounding manually.

Stacking guardrails used in the benchmark:

- Train and log each base model as its own candidate run before stacking.
- Keep the train/validation/test split frozen.
- Fit the meta-model only on out-of-fold or validation predictions.
- Do not tune on the test set.
- For RAG, evaluate retrieval before generation.

## Development

```bash
python tests/benchmark/token_eval_datasets.py
python tests/benchmark/token_eval_post_baseline.py
pytest
ruff check .
mypy src
```
