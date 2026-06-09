# Use with Codex

## Install

```bash
octopus install --runtime codex
```

Writes a Codex skill plus plain-markdown prompt-router fallbacks:

```text
~/.codex/skills/octopus-baseline/SKILL.md
~/.codex/skills/octopus-baseline/agents/openai.yaml
~/.codex/prompts/octopus-{baseline,plan,train,tune,status,resume}.md
~/.codex/.octopus-manifest.json
```

## Fast start

```bash
cd your-ml-project
octopus install --runtime codex
codex
```

In Codex:

```text
/skills
```

Choose **Octopus Baseline**, or invoke it directly:

```text
@octopus-baseline run the baseline workflow for this project
```

If your Codex surface does not load skills, paste the prompt-router fallback:

```bash
cat ~/.codex/prompts/octopus-baseline.md
```

## Manual setup

```bash
octopus init --runtime codex
octopus ask                 # or: octopus ask --from answers.yaml
octopus plan && octopus ml-plan && octopus tasks
octopus task next
octopus context --task "train the baseline" --profile training
codex
```

Prompt:

```text
This project uses Octopus. Run `octopus task next`, then read ONLY
`.octopus/context/current_context.md`. Implement the baseline first and stop
after the baseline script skeleton. Do not start the main model before a
baseline, do not change the split, and do not tune on the test set.
```

## Note on enforcement

Codex gets the prompt routers and the same CLI gates (`exp log` / `task start`
are blocked before a baseline). It does **not** get the `PreToolUse`
baseline-guard hook — that is Claude Code only. For runtime-level command
blocking, use Claude Code (see [Use with Claude Code](install-claude.md)).

## Uninstall

```bash
octopus uninstall --runtime codex
```
