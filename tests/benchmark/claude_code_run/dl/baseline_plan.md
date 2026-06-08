# Baseline Plan — Alpaca Image Classifier (Claude Code run)

Grounded in `.octopus/context/current_context.md`. BASELINE step only; the main
model is blocked until the baseline is logged.

## Decision
- Baseline model: **Pretrained MobileNet (frozen backbone)** — transfer learning.
- **No augmentation** in the baseline (add it only after the baseline exists).
- Metric: **macro_f1** + per-class recall (dataset is imbalanced).

## Steps
1. Use the frozen stratified train/val/test split. Do not re-split.
2. Run a **smoke test** on a tiny subset to catch pipeline bugs before full training.
3. Fine-tune only the classifier head on a frozen MobileNet backbone.
4. Monitor validation macro_f1 each epoch; watch the train/val gap (overfitting).
5. Evaluate on validation: macro_f1 + per-class recall. Keep the test set untouched.
6. Record seed and split paths.

## Guardrails (from context)
- Baseline before main model; one controlled change per experiment.
- No augmentation, no backbone unfreeze in the baseline.
- No tuning on the test set; check for train/val image leakage (duplicates).

## Next step (do not skip)
```bash
octopus exp ingest --run-dir runs/baseline_mobilenet --kind baseline
octopus exp profile
```
Stop here; do not start ResNet50 fine-tuning until the baseline is logged.
