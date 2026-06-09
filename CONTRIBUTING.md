# Contributing to Octopus

Thanks for helping improve Octopus. This project is an AI-agent workflow layer
for ML/DL/RAG projects: it helps Codex, Claude Code, and MCP clients follow a
baseline-first process with compact context, experiment memory, guardrails, JSON
tools, and MCP.

This guide explains how to set up the project, choose useful issues, make safe
changes, and prepare a pull request.

## Before You Start

Read these first:

- `README.md`: install and user-facing quickstart.
- `ARCHITECTURE.md`: project map, runtime model, state files, and extension
  points.
- `docs/README.md`: longer documentation index.

The most important project rule is baseline-first workflow discipline. Changes
should not encourage agents to skip baselines, tune on the test set, change data
splits casually, or stack complex models before measuring a simple baseline.

## Development Setup

Requirements:

- Python 3.11 or newer.
- Git.
- A shell environment that can run `make`.

Clone and install:

```bash
git clone https://github.com/quanai06/octopus.git
cd octopus

python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Verify the install:

```bash
octopus --help
make check
```

`make check` is the required local gate before opening a PR.

## Local Test Commands

Use the same commands as CI:

```bash
ruff check .
mypy src
pytest -q
```

Or run all of them:

```bash
make check
```

Benchmark/eval checks:

```bash
pytest -q tests/benchmark
python tests/benchmark/token_eval_datasets.py
python tests/benchmark/token_eval_post_baseline.py
```

Package build smoke:

```bash
python -m build
```

If `python -m build` is not installed:

```bash
python -m pip install --upgrade build
```

## Project Workflow For Changes

Use this loop:

1. Create a branch with a focused name.
2. Make the smallest change that solves the issue.
3. Add or update tests at the public behavior boundary.
4. Update docs when user behavior, commands, files, or tool schemas change.
5. Run `make check`.
6. Open a PR with a clear summary and verification notes.

Good branch names:

```text
fix/codex-install-message
docs/contributing-guide
feat/mcp-resource-example
test/baseline-guard-edge-case
```

## What To Work On

Good first contributions:

- Improve docs, examples, or troubleshooting.
- Add missing tests around an existing CLI behavior.
- Improve error messages with clear next commands.
- Add small examples for Codex or MCP usage.
- Improve benchmark documentation or result tables.

More advanced contributions:

- Add new task-type planning rules.
- Add a new experiment tracker reader.
- Add a new context profile or improve context section selection.
- Add a structured JSON tool.
- Add an MCP resource or improve MCP client examples.
- Improve baseline profiling and next-direction selection.

Avoid broad rewrites unless there is an issue discussing the design. Octopus is
small on purpose; most changes should be easy to review.

## Coding Standards

Use the existing style:

- Python source lives under `src/octopus/`.
- Tests live under `tests/`.
- CLI commands should stay thin and delegate reusable work to core modules.
- Prefer Pydantic models for structured inputs/outputs.
- Prefer stable file-backed state over hidden in-memory behavior.
- Prefer deterministic code over prompt-only logic.
- Keep user-facing messages direct and include the next command when possible.

Formatting and static checks are enforced by:

```bash
ruff check .
mypy src
```

Line length is 100 characters.

## Testing Guidelines

Add tests when changing:

- CLI command behavior.
- Generated files or templates.
- `.octopus/` state layout.
- Context selection.
- Experiment ingest/profile logic.
- Runtime install artifacts.
- JSON tool contracts.
- MCP server behavior.
- README/docs examples that are meant to be executable.

Prefer testing behavior through:

- Typer CLI runner for CLI commands.
- Public storage/planner functions for deterministic logic.
- JSON tool calls for machine-readable interfaces.
- MCP protocol messages for MCP behavior.

When fixing a bug, add a regression test that fails before the fix.

## Documentation Guidelines

Update documentation when you change user-visible behavior.

Common docs targets:

- `README.md`: quickstart, install, common workflows, release notes.
- `docs/guides/`: task-oriented usage guides.
- `docs/reference/cli.md`: command/option changes.
- `docs/reference/files.md`: generated file or `.octopus/` layout changes.
- `docs/reference/config.md`: config or intake schema changes.
- `ARCHITECTURE.md`: module boundaries, state lifecycle, extension points.
- `CONTRIBUTING.md`: contributor workflow changes.

Keep docs precise. Avoid promising behavior that is not implemented and tested.

## Runtime Artifact Changes

Runtime artifacts are generated from:

```text
src/octopus/install/artifacts.py
```

Codex and Claude Code are both supported, but they use different invocation
styles:

```text
Codex:       octopus-baseline
Claude Code: /octopus-baseline
```

Do not rewrite Claude Code behavior when making a Codex-only change, and do not
rewrite Codex prompt behavior when making a Claude-only change. If behavior must
change for both, update tests for both runtimes.

Runtime install changes should usually include tests in:

```text
tests/test_phase_3_install.py
```

## Adding A CLI Command

When adding a command:

1. Put command adapter code under `src/octopus/cli/commands/`.
2. Register it in `src/octopus/cli/main.py`.
3. Put reusable logic in `core/`, `planners/`, `experiments/`, `context/`, or
   `storage/` as appropriate.
4. Add tests through the CLI runner.
5. Add `--json` output if agents or automation will call it.
6. Update `docs/reference/cli.md` and README snippets if relevant.

A command should fail with a clear message and a next command, not a raw
traceback, for expected user errors.

## Adding A Structured Tool

Structured tools live under:

```text
src/octopus/tools/
```

To add a tool:

1. Add Pydantic input/output models in `contracts.py`.
2. Add a runtime handler in `runtime.py`.
3. Register the tool in `registry.py`.
4. Add CLI coverage through `octopus tool list --json` and
   `octopus tool call <name>`.
5. Add MCP coverage because the MCP server uses the same registry.
6. Document the tool in the relevant docs/reference page.

Tool outputs should be stable enough for agents to parse. Avoid returning only
human prose when structured fields are possible.

## Adding MCP Behavior

The MCP server is:

```text
src/octopus/mcp_server.py
```

MCP should wrap the existing tool/resource layer. Do not duplicate core logic in
the MCP transport.

When changing MCP behavior:

- Keep `initialize`, `tools/list`, `tools/call`, `resources/list`, and
  `resources/read` compatible.
- Add tests in `tests/test_tools_and_mcp.py`.
- Make sure server metadata uses the package version.
- Keep resource contents read-only unless a write operation is intentionally
  modeled as a tool.

## Adding Planning Or Baseline Rules

Planning rules should support disciplined baselines:

- ML/tabular/time-series: define fixed split or cross-validation strategy,
  leakage checks, metric choice, and a simple baseline.
- DL/images/text: define transfer/simple baseline, no premature augmentation,
  smoke test, macro/per-class metrics for imbalance when relevant.
- RAG: define labeled query set, BM25 or comparable retrieval baseline,
  chunking policy, Recall@k/MRR/source-hit metrics, and citation requirements
  before generation evaluation.

Useful files:

```text
src/octopus/planners/ml_rules.py
src/octopus/planners/ml_planner.py
src/octopus/templates/
tests/test_ml_plan.py
```

Do not add "baseline" text that is only motivational. It should produce concrete
constraints, tasks, metrics, or context that agents can follow.

## Experiment And Memory Changes

Experiment ingest and profiling should preserve reproducibility.

Useful files:

```text
src/octopus/experiments/ingest.py
src/octopus/experiments/baseline_profile.py
src/octopus/experiments/next_planner.py
src/octopus/experiments/selection.py
src/octopus/experiments/technique_library.py
src/octopus/storage/experiment_store.py
```

When changing experiment behavior:

- Keep baseline and candidate runs distinguishable.
- Preserve metrics and per-class metrics when available.
- Avoid ranking a technique without evidence from the run/profile.
- Update memory/report files in a way that agents can read later.
- Add tests for missing files, partial metrics, and malformed inputs.

## File And State Compatibility

Be careful with `.octopus/` file formats. Existing user projects may already
have these files.

If changing a state schema:

- Keep backward compatibility when possible.
- Add migration or tolerant parsing if old files are common.
- Document the change in `docs/reference/files.md` or
  `docs/reference/config.md`.
- Add tests using minimal old-format fixtures.

Internal state format versions are separate from the PyPI package version.

## Pull Request Checklist

Before opening a PR, confirm:

- The change has a focused scope.
- Tests were added or updated when behavior changed.
- `make check` passes.
- Documentation was updated if user-visible behavior changed.
- Codex and Claude Code invocation differences were preserved.
- Structured outputs remain stable if tools/MCP changed.
- The PR description explains why the change is needed.

Suggested PR verification section:

```text
Verification:
- make check
- python -m build
- octopus --help
```

Only include commands you actually ran.

## Commit And PR Style

Use clear, small commits. Good commit messages:

```text
fix: use codex prompt name in install message
docs: add architecture and contributing guides
test: cover MCP initialize server version
feat: add structured baseline profile tool output
```

PR descriptions should include:

- What changed.
- Why it changed.
- How it was tested.
- Any compatibility or migration notes.

## Release Process

Maintainers publish releases. Contributors normally do not need PyPI access.

Release checklist:

```bash
make check
python -m build
git tag vX.Y.Z
git push origin vX.Y.Z
```

Then publish the GitHub Release. The PyPI workflow uses Trusted Publishing.

PyPI never allows re-uploading the same version. If a version was already
published, bump `pyproject.toml` to a new unused version, commit, tag, and
publish a new release.

## Reporting Bugs

When reporting a bug, include:

- OS and Python version.
- Octopus version: `octopus --version` if available, or `python -m pip show
  cli-octopus`.
- The command you ran.
- The expected result.
- The actual output or traceback.
- Whether the project already had a `.octopus/` directory.
- A minimal reproduction if possible.

Do not include private datasets, API keys, tokens, or proprietary model outputs.

## Security And Privacy

Octopus writes project state into the user's repository. Contributors should
avoid adding behavior that uploads, phones home, or stores secrets.

Do not commit:

- API keys or credentials.
- Private datasets.
- Large model checkpoints.
- Generated virtualenvs, build artifacts, caches, or `__pycache__` files.

If you find a security-sensitive issue, open a minimal report without secrets or
contact the maintainer privately if public disclosure would expose users.

## Maintainer Priorities

The project should stay:

- Baseline-first.
- Agent-friendly.
- Deterministic where possible.
- Small enough to understand.
- Useful without requiring a specific training framework.
- Compatible with Codex, Claude Code, and MCP clients.

When in doubt, prefer a small well-tested workflow improvement over a broad
feature that only works in one demo.
