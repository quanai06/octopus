# Octopus Architecture

Octopus is a baseline-first workflow layer for AI coding agents working on
ML/DL/RAG projects. It is not a model training framework and it does not own the
user's training loop. Its job is to keep Codex, Claude Code, and MCP clients
grounded in a reproducible project workflow:

```text
requirements -> plans -> tasks -> bounded context -> baseline -> ingest/profile
-> selected next direction -> one controlled improvement
```

The central design idea is simple: agents should not rely on a long prompt or
session memory to remember ML discipline. Octopus writes the project state to
disk, exposes it through CLI commands and structured tools, then routes the host
agent back through that state before it writes or runs code.

## System Boundaries

Octopus owns:

- Project intake and persisted project state.
- Generated planning documents for baseline-first ML/DL/RAG work.
- Task gates that make the baseline the first unblocked work item.
- Token-bounded working context in `.octopus/context/current_context.md`.
- Experiment memory and baseline profiling after real runs.
- Codex prompt routers and Claude Code slash commands/subagents.
- Machine-readable CLI output, JSON tool contracts, and an MCP stdio server.

Octopus does not own:

- Dataset download, data licensing, or dataset hosting.
- The user's final model architecture or training framework.
- GPU scheduling, experiment execution infrastructure, or cloud deployment.
- Metric correctness inside user training scripts beyond what can be ingested
  and analyzed from run artifacts.

## Runtime Model

Octopus has three layers:

```text
Host agent runtime
  Codex prompt files, Claude Code commands/subagents, MCP clients

Octopus interface layer
  Typer CLI, JSON tool registry, MCP stdio server

Octopus project state
  .octopus/ state, generated planning docs, tasks, context, memory, reports
```

The host agent remains responsible for natural-language reasoning and code
editing. Octopus supplies the deterministic workflow, file state, guardrails, and
machine-readable interfaces.

## Main User Lifecycle

The normal Codex path is:

```bash
python -m pip install cli-octopus
octopus install --runtime codex
cd your-ml-project
codex
```

Then inside Codex:

```text
octopus-baseline
```

The installed `octopus-baseline` prompt router tells Codex to:

1. Initialize `.octopus/` if needed.
2. Inspect status and collect missing project facts.
3. Render requirements, ML design, data strategy, experiment plan, and tasks.
4. Build `.octopus/context/current_context.md`.
5. Read only the bounded working context.
6. Write the baseline plan and baseline script skeleton.
7. Stop before training unless the user explicitly asks to run it.

After a real baseline run, the intended loop is:

```bash
octopus exp ingest --run-dir <run_dir> --kind baseline
octopus exp profile
octopus exp next
octopus exp choose D1
octopus context --direction D1 --profile training
```

The next implementation should make exactly one controlled change and then
ingest/profile again.

## Source Layout

```text
src/octopus/
  cli/             Typer application and command adapters
  context/         context selection, token estimation, code/file scanning
  core/            paths, schemas, file helpers, guards, workflow defaults
  experiments/     run ingest, baseline analysis, next-direction selection
  install/         Codex/Claude artifact rendering and installation
  planners/        requirement, ML, task, experiment plan generation
  storage/         project/task/session/experiment persistence
  templates/       Jinja templates for generated planning files
  tools/           structured JSON tool contracts and runtime handlers
  mcp_server.py    MCP stdio server backed by the same tool/resource layer
```

The CLI should stay thin. Most command files in `src/octopus/cli/commands/`
validate options, call a core/planner/storage function, and format the result.
Reusable behavior should live outside the CLI layer so it can also be exposed by
JSON tools and MCP.

## Persistent Project Files

Octopus stores project state in the target project, not in the package install:

```text
.octopus/
  config.yaml
  project_state.json
  tasks.json
  context/current_context.md
  experiments/index.yaml
  memory/experiments.md
  memory/best_runs.md
  memory/failures.md
  memory/decisions.md
  reports/baseline_profile.md
  reports/experiment_report.md
  plans/next_steps.md
  plans/next_steps.yaml
  plans/selected_direction.yaml
  session/current.json
  session/current.md
```

Root-level generated planning files include:

```text
requirements.md
ml_design.md
data_strategy.md
experiment_plan.md
compute_budget.md
tasks.md
AGENTS.md
CLAUDE.md
```

`.octopus/` is the source of truth for state. Root planning files are optimized
for humans and agents to read.

## Command Architecture

The CLI entrypoint is `octopus.cli.main:app`.

Top-level commands:

- `octopus init`: create `.octopus/`, runtime docs, and config.
- `octopus ask`: collect or load project facts.
- `octopus plan`: render general planning docs.
- `octopus ml-plan`: render ML/DL/RAG-specific baseline strategy.
- `octopus tasks`: render task files and task state.
- `octopus task next`: return the next unblocked task.
- `octopus context`: build the bounded working context.
- `octopus status`: summarize project readiness and next action.
- `octopus session`: persist/resume working session state.
- `octopus exp`: ingest runs, analyze/profile, select next directions.
- `octopus tool`: list/call structured JSON tools.
- `octopus mcp`: run the MCP stdio server.
- `octopus install` / `octopus uninstall`: manage Codex/Claude artifacts.

Commands that are likely to be called by agents should support stable `--json`
output when practical. Human-formatted Rich output can exist, but it should not
be the only interface for automation.

## Planning And Baseline Logic

Planning starts from `ProjectState` in `src/octopus/core/schemas.py`.

The planners render documents from templates and rules:

- `requirement_planner.py`: project summary and requirements.
- `ml_planner.py` + `ml_rules.py`: task-type-specific ML/DL/RAG guidance.
- `task_planner.py`: task list and baseline-first sequencing.
- `experiment_advisor.py`, `experiment_report.py`: post-run guidance.

The baseline contract should remain explicit:

- Start with a simple reproducible baseline.
- Use fixed train/validation/test rules.
- Do not tune on the test set.
- Report task-appropriate metrics, not only accuracy.
- Change exactly one thing per experiment after the baseline.
- For RAG, validate retrieval quality before generation/prompt tuning.

Baseline rules should be encoded in generated docs/tasks whenever possible, not
only in prompt prose.

## Context Builder

`src/octopus/context/builder.py` builds `.octopus/context/current_context.md`.

The builder combines:

- Project snapshot from persisted state.
- Relevant sections from generated planning files.
- Experiment memory and selected next direction when present.
- Small snippets from relevant code files.
- Token estimates through `tiktoken` when available.

Context profiles are defined in `src/octopus/context/profiles.py`:

- `planning`
- `training`
- `debugging`
- `review`

The context file is deliberately a compact working surface. It is not a full
repository dump. The goal is to reduce prompt token load while keeping the agent
grounded in the exact task and constraints.

## Experiment Memory

Experiment ingest starts in `src/octopus/experiments/ingest.py`.

Supported inputs include:

- `metrics.json`
- `classification_report.json` or `report.json`
- `trainer_state.json`
- `config.yaml` or `config.yml`
- `train.log` or `training.log`
- Tracker exports from MLflow, W&B, or TensorBoard when detectable

Records are written through `src/octopus/storage/experiment_store.py` into
`.octopus/experiments/index.yaml`. Memory/report files summarize the useful
parts for later agent sessions.

After a baseline exists, `octopus exp profile` diagnoses:

- target gap
- weak classes or weak metrics
- overfitting/underfitting signals
- data imbalance or leakage risks when visible
- ranked next techniques
- techniques that should not be tried yet

This is the "post-check" stage: it prevents the agent from blindly stacking
more complex models before understanding what the baseline actually failed at.

## Runtime Installation

Runtime artifacts are generated from `src/octopus/install/artifacts.py`.

Codex receives prompt routers under:

```text
~/.codex/prompts/
```

Claude Code receives slash commands and subagents under:

```text
~/.claude/commands/
~/.claude/agents/
```

Claude Code also receives the baseline guard hook in settings when installed.
Codex and Claude artifacts should stay behaviorally aligned, but their syntax is
different:

- Codex prompt name: `octopus-baseline`
- Claude slash command: `/octopus-baseline`

Do not change one runtime's invocation style to match the other.

## Structured Tools And MCP

The structured tool layer lives in `src/octopus/tools/`.

The registry exposes:

- `octopus_status`
- `octopus_task_next`
- `octopus_build_context`
- `octopus_ingest_run`
- `octopus_profile_baseline`

Each tool has:

- a Pydantic input model
- a Pydantic output model
- a JSON schema generated from the model
- a runtime handler that calls the same core code used by the CLI

The MCP server in `src/octopus/mcp_server.py` exposes those tools over stdio and
also exposes project resources. MCP should remain a transport layer, not a
separate implementation of Octopus logic.

## Guardrails

Guardrails exist at several levels:

- CLI guards in `src/octopus/core/guards.py` stop commands when required state
  is missing.
- Generated planning files and task state encode baseline-first sequencing.
- Runtime prompt routers tell the host agent to read current context before work.
- Claude's baseline guard hook blocks main-model training before baseline state
  exists.
- Experiment profiling discourages tuning before diagnosis.

Guardrails are useful only if they are inspectable and recoverable. Prefer clear
messages and next commands over silent failures.

## Testing Strategy

The local gate is:

```bash
make check
```

That runs:

```bash
ruff check .
mypy src
pytest -q
```

Test coverage is organized around behavior:

- CLI setup and command behavior.
- Project initialization and state files.
- Planning and ML plan generation.
- Context building and token estimation.
- Baseline guard behavior.
- Experiment ingest/profile/selection.
- Runtime install artifacts for Codex and Claude Code.
- JSON tools and MCP protocol behavior.
- Benchmark/eval scenarios under `tests/benchmark/`.

When adding functionality, prefer testing through the public CLI/tool boundary
when possible, then add lower-level tests for edge cases.

## Release And Packaging

Packaging is configured in `pyproject.toml`.

The package name is:

```text
cli-octopus
```

The console script is:

```text
octopus
```

GitHub Actions contains:

- `.github/workflows/ci.yml`: runs the local check/build gate.
- `.github/workflows/publish.yml`: publishes releases to PyPI through Trusted
  Publishing.

PyPI does not allow reusing a version. If publishing fails with `File already
exists`, bump `pyproject.toml` to a new unused version, commit, tag, and publish
a new GitHub Release.

## Extension Points

Good places to extend Octopus:

- New task-type rules in `src/octopus/planners/ml_rules.py`.
- New generated plan sections through templates in `src/octopus/templates/`.
- New context profile rules in `src/octopus/context/profiles.py`.
- New experiment technique suggestions in
  `src/octopus/experiments/technique_library.py`.
- New tracker readers in `src/octopus/experiments/trackers.py`.
- New structured tools by adding contracts, runtime handlers, registry entries,
  CLI/MCP tests, and docs.
- New runtime artifacts through `src/octopus/install/artifacts.py`, with care to
  preserve Codex/Claude invocation differences.

Avoid adding behavior only to a prompt if the CLI can own it deterministically.
Prompt text should route the agent; core workflow decisions should live in code
or persisted state.

## Design Principles

- Baseline first: no main model before a reproducible baseline exists.
- Fixed evaluation: no test tuning and no casual split changes.
- One controlled change: experiments should isolate a single idea.
- Small working context: agents should read the right context, not everything.
- File-backed memory: project state should survive session resets.
- Structured interfaces: automation should use JSON schemas and stable outputs.
- Runtime portability: Codex, Claude Code, and MCP clients should share the same
  Octopus core.
- Human recoverability: every guard or failure should point to the next command.
