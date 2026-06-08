# Ingest runs from MLflow / W&B / TensorBoard

`octopus exp ingest` auto-detects common tracker run directories, so you can point
it at a tracker run instead of writing `metrics.json` by hand.

```bash
octopus exp ingest --run-dir mlruns/0/<run_id> --kind baseline   # MLflow
octopus exp ingest --run-dir wandb/run-<id>                      # Weights & Biases
octopus exp ingest --run-dir runs/<name>                         # TensorBoard
octopus exp ingest --run-dir runs/E001 --tracker none            # plain files only
```

## How detection works

`--tracker` defaults to `auto`. Detection by directory contents:

| Tracker | Detected by | Parsed from |
|---|---|---|
| `mlflow` | `meta.yaml` + `metrics/` dir | last value of each `metrics/<name>` file, `params/`, `meta.yaml` run name |
| `wandb` | a `wandb-summary.json` | numeric summary keys (internal `_*` skipped), `config.yaml` params |
| `tensorboard` | `events.out.tfevents.*` | last scalar per tag (needs the optional `tensorboard` package) |

MLflow and W&B parse from disk with **no extra dependency**. TensorBoard needs
`pip install tensorboard`; without it, ingest reports a clear install hint.

Detected runs are tagged with their source (e.g. `source:mlflow`). Explicit
`--metrics` / `--report` files always take precedence over tracker values.

## Plain run directories

Without a tracker, `--run-dir` can contain:

```text
metrics.json               # flat {metric: number}
classification_report.json # sklearn-style per-class report
trainer_state.json         # HF Trainer log_history (fallback)
config.yaml                # model/dataset metadata
```

## After ingest

```bash
octopus exp analyze E001     # rule-based diagnosis + training review
octopus exp profile          # baseline understanding + ranked techniques
```
