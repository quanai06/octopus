# Octopus Documentation

Octopus is a Python CLI that turns an ML/DL/RAG project into a **baseline-first**
workflow for Claude Code and Codex: capture requirements, render planning files,
build a compact task context, track experiments, and stop the agent from jumping
to the main model before a real baseline exists.

These docs follow the [Diátaxis](https://diataxis.fr/) structure.

## Start here
- [Getting Started](getting-started.md) — a full first run, end to end (tutorial).
- [Concepts](concepts.md) — the mental model: baseline-first, `.octopus/`, context,
  sessions, and the host-runtime architecture (explanation).

## Guides (task-oriented how-to)
- [Use with Claude Code](guides/install-claude.md)
- [Use with Codex](guides/install-codex.md)
- [Headless / non-interactive setup](guides/headless-setup.md)
- [The tuning loop (profile → next → choose)](guides/tuning-loop.md)
- [Ingest runs from MLflow / W&B / TensorBoard](guides/tracker-ingest.md)
- [Resume work after a context reset](guides/resume-session.md)

## Reference (look-up)
- [CLI reference](reference/cli.md) — every command and option.
- [Configuration reference](reference/config.md) — `project_state.json`,
  `config.yaml`, and the `answers.yaml` intake file.
- [Generated files](reference/files.md) — the `.octopus/` layout and root artifacts.

## Project docs (outside `docs/`)
- `README.md` — Codex-first overview and quickstart.
- `ROADMAP_GSD_FOR_ML.md` — roadmap and phase status.
- `phase_1.md` … `phase_4.md` — implementation notes per phase.
- `eval_token_and_compliance.md` — token + compliance eval protocol.
