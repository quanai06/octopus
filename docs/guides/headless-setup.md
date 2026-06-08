# Headless / non-interactive setup

`octopus ask` is interactive (it needs a TTY). For an agent's Bash tool, CI, or
the benchmark, seed project state from a file instead:

```bash
octopus ask --from answers.yaml
```

The file is a YAML (or JSON) mapping of `ProjectState` fields. Values **merge onto**
existing state; `compute` is merged as a nested mapping. Unknown-but-valid fields
are accepted; invalid values fail with a clear error and a non-zero exit.

## Example `answers.yaml`

```yaml
project_name: Vietnamese Emotion Classifier
project_goal: Classify Vietnamese social posts by emotion.
target_users: ML engineers
project_type: machine learning        # software | machine learning | deep learning | rag | research
task_type: text_classification        # see reference/config.md for the list
input_type: text
output_type: emotion_label
dataset_status: available             # available | partial | not_ready
dataset_size_note: ~50k samples
has_labels: true
has_class_imbalance: true
main_metric: macro_f1
baseline_model: TF-IDF + Logistic Regression
target_score: 0.82
runtime: [claude, codex]
compute:
  has_gpu: false
  environment: local
  budget_note: CPU only
```

All fields are optional and have defaults; see
[Configuration reference](../reference/config.md) for the full schema.

## Full headless flow

```bash
octopus init --runtime claude,codex --force
octopus ask --from answers.yaml
octopus plan --force
octopus ml-plan --force
octopus tasks --force
octopus context --task "train the baseline" --profile training
```

This is exactly the path `/octopus-baseline` uses, so the one-shot command works
without a human at the prompt.
