# Use with Claude Code

Embed the baseline-first workflow into Claude Code: slash commands, subagents,
and a hard guard hook.

## Install

```bash
octopus install --runtime claude
```

Writes:

```text
~/.claude/commands/octopus-{baseline,plan,train,tune,status,resume}.md
~/.claude/agents/octopus-{baseline-runner,experiment-analyst,tuner,data-auditor,rag-evaluator}.md
~/.claude/settings.json            # baseline-guard PreToolUse hook (merged, idempotent)
~/.claude/.octopus-manifest.json
```

Existing `settings.json` keys are preserved; reinstalling never duplicates the
hook. `--home <dir>` installs into `<dir>/.claude` instead of your home (useful
for testing).

## Fast start

```bash
cd your-ml-project
octopus install --runtime claude
claude
```

In Claude Code:

```text
/octopus-baseline
```

This runs the one-shot setup → baseline path: init if needed, gather facts and run
`octopus ask --from answers.yaml`, then `plan/ml-plan/tasks --force`, `task next`,
`context`, read `current_context.md`, write the baseline plan + script skeleton,
and stop before training.

## Slash commands

| Command | Does |
|---|---|
| `/octopus-baseline` | one-shot setup → first baseline task |
| `/octopus-plan` | intake → plan → ml-plan → tasks |
| `/octopus-train` | baseline-first training loop (ingest → profile) |
| `/octopus-tune` | profile → next → choose → implement one technique |
| `/octopus-status` | project snapshot + next action |
| `/octopus-resume` | restore context after a reset |

## Subagents

Claude can delegate to:

- `octopus-baseline-runner` — establish + ingest the first baseline.
- `octopus-experiment-analyst` — analyze/profile a finished run.
- `octopus-tuner` — implement exactly one selected direction.
- `octopus-data-auditor` — split / leakage / imbalance audit.
- `octopus-rag-evaluator` — retrieval eval + citation/faithfulness.

## Baseline-guard hook

A `PreToolUse` hook on the Bash tool blocks main-model training before a baseline
exists. These exit with code `2` until you log a baseline:

```text
python train.py            accelerate launch train.py     torchrun ...
python train_phobert.py    deepspeed train.py             any fine-tune command
```

Baseline scripts and non-training commands pass through. The hook command is
`python -m octopus.install.hooks baseline-guard`.

## Manual setup

```bash
octopus init --runtime claude
octopus ask                 # or: octopus ask --from answers.yaml
octopus plan && octopus ml-plan && octopus tasks
octopus task next
octopus context --task "train the baseline" --profile training
claude
```

Prompt:

```text
This project uses Octopus. Run `octopus task next`, then read ONLY
`.octopus/context/current_context.md`. Implement the baseline first and stop
after the baseline script skeleton. Do not start the main model before a
baseline, do not change the split, and do not tune on the test set.
```

## Uninstall

```bash
octopus uninstall --runtime claude
```

Manifest-driven: only the files Octopus wrote are removed, and the hook is taken
back out of `settings.json`.
