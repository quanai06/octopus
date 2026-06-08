# Phase 3 — Installer + Command Layer

> How this phase was built. Part of the "GSD for ML/DL/RAG" direction
> (`ROADMAP_GSD_FOR_ML.md`). Host-runtime model: artifacts are installed into
> Claude Code / Codex; those runtimes run the LLM loop, Octopus stays the
> deterministic brain.

## Goal

Embed Octopus into Claude Code and Codex so users are steered into the
baseline-first workflow with a small token surface, and so the baseline-first
rule is enforced *inside* the runtime (not only in the CLI).

## What was built

### 1. `octopus/install/` package
- `layout.py` — runtime home mapping. `claude -> <home>/.claude`,
  `codex -> <home>/.codex`. `home` defaults to `Path.home()`, overridable with
  `--home` (used by tests). Path helpers for commands/agents/settings/prompts +
  `parse_runtimes()` validation.
- `artifacts.py` — the source content as data: `CommandRouter` definitions and
  renderers (`render_command_router` for Claude frontmatter, `render_codex_prompt`
  for plain-markdown Codex prompts). `AGENT_DEFS` is empty here; Phase 4 fills it.
- `installer.py` — `install()` / `uninstall()`. Writes routers per runtime,
  merges the baseline-guard hook into Claude `settings.json`, and records a
  per-runtime `.octopus-manifest.json` so uninstall removes exactly what it wrote.
- `hooks.py` — the PreToolUse hook handler, run as
  `python -m octopus.install.hooks baseline-guard`.

### 2. Command routers (thin, low-token)
Installed as `~/.claude/commands/octopus-*.md` (invoked `/octopus-*`) and
`~/.codex/prompts/octopus-*.md`:
- `/octopus-plan` — intake → plan → ml-plan → tasks → context.
- `/octopus-train` — baseline-first training loop (ingest → profile).
- `/octopus-tune` — profile baseline → next → choose → implement one technique.
- `/octopus-status` — status + next + summary.

Each router just points the model at the `octopus` CLI and `.octopus/` files, so
the runtime spends few tokens and follows the deterministic workflow.

### 3. Baseline-guard hook (runtime enforcement)
A Claude Code `PreToolUse` hook on the `Bash` tool. On each shell call it reads
the command from stdin JSON; if the command looks like main-model training
(`train.py`, `trainer`, `.fit(`, `torchrun`, `fine-tune`, ...) and the project
requires a baseline that does not exist yet, it prints a reason to stderr and
exits `2` to **block** the call. It reuses the exact CLI rule
(`requires_baseline_gate` + `has_completed_baseline`). Non-training commands and
non-Octopus projects pass through (exit 0).

### 4. CLI surface
- `octopus install --runtime claude,codex [--home <dir>] [--force]`
- `octopus uninstall --runtime claude,codex [--home <dir>]`

## How I verified the runtime formats

Before generating artifacts I confirmed the exact on-disk formats with the
`claude-code-guide` agent: flat slash commands at `~/.claude/commands/<name>.md`
(frontmatter `description`, `allowed-tools`, `model`); subagents at
`~/.claude/agents/<name>.md`; hooks in `settings.json` under
`hooks.PreToolUse[].matcher` + `hooks[].{type,command}`, blocking via exit code 2;
Codex custom prompts at `~/.codex/prompts/<name>.md`.

## Design decisions
- **Routers are managed artifacts**: every (re)install refreshes them in place.
- **Settings merge is non-destructive**: existing `settings.json` keys are kept;
  the hook is added once (idempotent) and removed cleanly on uninstall.
- **Manifest-driven uninstall**: only files we recorded are deleted.
- **Hook as a Python module**, not brittle shell+yaml parsing, so it reuses the
  real workflow rule and is unit-testable.

## Tests (`tests/test_phase_3_install.py`, 11)
Commands + hook written; Codex prompts are plain markdown; hook is idempotent;
existing settings preserved; uninstall removes files + hook; baseline-guard
blocks training without a baseline, allows it after one, ignores non-training
commands and non-Octopus dirs; CLI install/uninstall + unknown-runtime rejection.

## Verification
`make check` green: ruff + mypy clean, 104 tests pass. Live smoke test installed
both runtimes into a temp home and confirmed the hook landed in `settings.json`.
