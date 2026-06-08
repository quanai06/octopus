# Resume work after a context reset

Session memory keeps short-term state in `.octopus/session/` so a Claude/Codex
session can be restored after it loses context.

## Start a session

```bash
octopus session start --goal "beat the TF-IDF baseline"
```

It auto-captures from the workflow as you go:

- `octopus task start <id>` → records the current task,
- `octopus exp choose D<n>` → records the selected direction,
- `octopus exp ingest …` → records the last run.

You can also log notes manually:

```bash
octopus session log "tried class weights, fear recall up" --kind note
octopus session show
```

`--kind` is one of `note | task | direction | run | decision`.

## Restore after a reset

```bash
octopus resume
```

Prints the active session summary (goal, current task, selected direction, last
run, recent events) and which restore files exist
(`current_context.md`, `selected_direction.yaml`, `baseline_profile.md`,
`next_steps.md`), then tells the agent to continue only the in-progress work.

In a runtime with the routers installed, just run `/octopus-resume` (Claude Code)
or `octopus-resume` (Codex).

## End a session

```bash
octopus session end          # archives to .octopus/session/<id>.json
```

## Session vs long-term memory

This is **RAM**, not the archive. Long-term experiment history lives in
`.octopus/experiments/` and `.octopus/memory/`; the session is just what is
happening right now.
