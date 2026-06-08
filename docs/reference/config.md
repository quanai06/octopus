# Configuration Reference

## Project state — `.octopus/project_state.json`

Written by `octopus ask` (or `ask --from`). Schema (`ProjectState`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `project_name` | str | `""` | |
| `project_goal` | str? | — | |
| `target_users` | str? | — | |
| `project_type` | str | `software` | `software` \| `machine learning` \| `deep learning` \| `rag` \| `research` (or custom) |
| `task_type` | str? | — | see list below |
| `input_type` | str? | — | `text` \| `image` \| `tabular` \| `audio` \| `video` \| `multimodal` \| `documents` |
| `output_type` | str? | — | free text (e.g. `emotion_label`, `answer_with_source`) |
| `dataset_status` | str? | — | `available` \| `partial` \| `not_ready` |
| `dataset_size_note` | str? | — | |
| `has_labels` | bool? | — | |
| `has_class_imbalance` | bool? | — | drives imbalance handling |
| `main_metric` | str? | — | `macro_f1` \| `accuracy` \| `MAE` \| `RMSE` \| `Recall@k` \| `MRR` (or custom) |
| `baseline_model` | str? | — | selected baseline |
| `target_score` | float? | — | used for headroom/stop conditions |
| `baseline_required` | bool | `true` | when true, baseline-first gates are enforced |
| `runtime` | list[str] | `[]` | e.g. `[claude, codex]` |
| `compute` | object | — | see below |
| `created_at` / `last_updated` | datetime | now | managed automatically |

`compute`:

| Field | Type | Default |
|---|---|---|
| `has_gpu` | bool | `false` |
| `environment` | str? | — (`local`/`colab_t4`/`kaggle`/`server`/…) |
| `budget_note` | str? | — |
| `deadline` | str? | — |

### `task_type` values
`text_classification`, `image_classification`, `regression`, `retrieval`,
`recommendation`, `forecasting`, `clustering`, `anomaly_detection`, `rag`.
Each maps to baseline models, metrics, risks, and first experiments
(`octopus.planners.ml_rules`). Unknown values fall back to generic rules.

## `answers.yaml` (headless intake)

Any subset of the fields above, as YAML or JSON. Values merge onto existing
state; `compute` is merged as a nested mapping. See
[Headless setup](../guides/headless-setup.md) for an example.

## Octopus config — `.octopus/config.yaml`

Small bookkeeping file written by `init`:

```yaml
version: "0.1.0"
runtime: [claude, codex]
created_at: 2026-06-08T...
last_updated: 2026-06-08T...
```

## Runtime config touched by `install`

- Claude: `~/.claude/settings.json` gains a `hooks.PreToolUse` entry running
  `python -m octopus.install.hooks baseline-guard` (matcher `Bash`). Merge is
  idempotent and non-destructive; uninstall removes only that entry.
- A `~/.<runtime>/.octopus-manifest.json` records exactly which files were
  installed, so uninstall is precise.
