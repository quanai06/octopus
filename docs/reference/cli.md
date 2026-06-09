# CLI Reference

Every Octopus command and option. Run `octopus <command> --help` for the live
version. Commands exit `0` on success and `1` on a blocked/invalid operation
(for example logging a main model before a baseline).

## Project setup

### `octopus init`
Create `.octopus/` and the generated planning files.

| Option | Default | Description |
|---|---|---|
| `--runtime TEXT` | `claude,codex` | Comma-separated runtimes to generate files for. Use `none` for neither. |
| `--force` | off | Overwrite without prompting. |

### `octopus ask`
Capture requirements into `.octopus/project_state.json`.

| Option | Default | Description |
|---|---|---|
| `--reset` | off | Ignore existing state and start fresh. |
| `--from PATH` | — | Non-interactive intake from a YAML/JSON answers file. |

### `octopus plan` / `octopus ml-plan` / `octopus tasks`
Render planning artifacts. Each takes `--force` to overwrite.

- `plan` → `requirements.md`
- `ml-plan` → `ml_design.md`, `experiment_plan.md`, `data_strategy.md`, `compute_budget.md`
- `tasks` → `tasks.md` + `.octopus/tasks.json`

### `octopus sync`
Regenerate `CLAUDE.md` / `AGENTS.md` from current state.

| Option | Default | Description |
|---|---|---|
| `--runtime TEXT` | both | Limit to `claude` or `codex`. |

### `octopus status`
Print a project snapshot.

| Option | Default | Description |
|---|---|---|
| `--json` | off | Print a stable machine-readable result envelope. |

## Context

### `octopus context [INSPECT_ARG]`
Build `.octopus/context/current_context.md`. Pass `inspect` to print the current
context instead of rebuilding.

| Option | Default | Description |
|---|---|---|
| `--task TEXT` | — | Current task description (focuses the context). |
| `--profile TEXT` | `training` | `planning` \| `training` \| `debugging` \| `review`. |
| `--budget INTEGER` | `6000` | Soft token budget for selected sections. |
| `--full` | off | Include all planning sections. |
| `--direction TEXT` | — | Build a direction-specific context (e.g. `D1`). |
| `--target TEXT` | `codex` | Direction context target: `codex` or `claude`. |
| `--json` | off | Print a stable machine-readable result envelope. |

## Tasks — `octopus task`

| Subcommand | Description |
|---|---|
| `list` | Show all tasks and status. |
| `next` | Show the first unblocked task. |
| `start <id>` | Mark a task in-progress (blocked if dependencies unmet). |
| `done <id>` | Mark a task done. |
| `reopen <id>` | Reopen a done task. |

`task start T020` (main model) is blocked until `T012` (baseline logged) is done.
`task next --json` returns the same next-task result as structured tool
`octopus_task_next`.

## Experiments — `octopus exp`

| Subcommand | Key options | Description |
|---|---|---|
| `init` | — | Initialize experiment tracking files. |
| `log` | `--name`, `--kind`, `--metric k=v` (repeat), `--model`, `--dataset`, `--note`, `--status` | Log an experiment by hand. |
| `ingest` | `--run-dir`, `--metrics`, `--report`, `--config`, `--name`, `--kind`, `--model`, `--dataset`, `--note`, `--tag`, `--tracker` | Ingest a run dir (auto-detects MLflow/W&B/TensorBoard). |
| `analyze <id>` | — | Rule-based diagnosis + training review. |
| `profile` | `--exp`, `--top-k` | Baseline understanding + ranked techniques → `baseline_profile.md`. |
| `next` | `--top-k`, `--output` | Ranked next directions → `next_steps.{md,yaml}`. |
| `choose <id>` | — | Select a direction (e.g. `D1`). |
| `list` | — | Table of logged experiments. |
| `compare` | `--metric` | Rank experiments by a metric. |
| `diagnose` | `--exp` | Pattern/cause/actions for one run. |
| `suggest` | — | Rule-based next-step suggestion. |
| `report` | — | Write `experiment_report.md`. |

`--kind` for `log`: `auto` \| `baseline` \| `candidate` \| `main` \| `other`.
`ingest` also accepts `ablation` \| `debug`. `--tracker`: `auto` \| `mlflow` \|
`wandb` \| `tensorboard` \| `none`. Logging a main/candidate before a completed
baseline is blocked.

`exp ingest --json` and `exp profile --json` return stable JSON envelopes. A
completed baseline ingest also marks `T010`/`T011`/`T012` done, matching
`exp log --kind baseline`.

## Structured tools and MCP

### `octopus tool list`
List function-calling compatible tool contracts.

| Option | Default | Description |
|---|---|---|
| `--json` | off | Print tool names plus input/output JSON schemas. |

### `octopus tool call <name>`
Call a structured tool with JSON arguments.

| Option | Default | Description |
|---|---|---|
| `--input PATH` | — | JSON object file containing tool arguments. |
| `--input-json TEXT` | — | Inline JSON object containing tool arguments. |
| `--json` | on | Print a result envelope: `ok`, `tool`, `result` or `error`. |

Available tools:

| Tool | Purpose |
|---|---|
| `octopus_status` | Project snapshot, generated files, context metadata, next task. |
| `octopus_task_next` | Next unblocked task and start command. |
| `octopus_build_context` | Build task or direction context under a token budget. |
| `octopus_ingest_run` | Ingest a run into experiment memory. |
| `octopus_profile_baseline` | Profile the completed baseline and rank next techniques. |

### `octopus mcp`
Run the Octopus MCP server over stdio. It exposes the same tools and these
readable resources:

| Resource | Meaning |
|---|---|
| `octopus://context/current` | Latest `current_context.md`. |
| `octopus://memory/experiments` | Long-term experiment memory. |
| `octopus://session/current` | Active session summary. |
| `octopus://reports/baseline_profile` | Latest baseline profile. |
| `octopus://plans/next_steps` | Ranked next experiment directions. |

## Sessions — `octopus session`

| Subcommand | Options | Description |
|---|---|---|
| `start` | `--goal` | Start a session. |
| `show` | — | Show the active session. |
| `log <msg>` | `--kind` | Append an event (`note`/`task`/`direction`/`run`/`decision`). |
| `end` | — | End + archive the session. |

### `octopus resume`
Print a restore summary for a runtime that lost context. No options.

## Runtime install

### `octopus install` / `octopus uninstall`

| Option | Default | Description |
|---|---|---|
| `--runtime TEXT` | `claude,codex` | Comma-separated runtimes. |
| `--home PATH` | your home | Base dir containing `.claude`/`.codex` (for testing). |
| `--force` | off | (install) Overwrite managed files. |

See [Use with Claude Code](../guides/install-claude.md) and
[Use with Codex](../guides/install-codex.md) for what gets written.
