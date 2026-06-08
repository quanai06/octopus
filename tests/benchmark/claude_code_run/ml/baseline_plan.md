# Baseline Plan — Vietnamese Emotion Classifier (Claude Code run)

Grounded in `.octopus/context/current_context.md` (task: train the baseline).
This is the BASELINE step only. The main model (PhoBERT) is blocked until the
baseline is logged (T020 depends on T012).

## Decision
- Baseline model: **TF-IDF + Logistic Regression** (from the selected baseline).
- Metric: **macro_f1** (primary) + per-class recall + confusion matrix; not accuracy.
- Class imbalance: handle with `class_weight="balanced"` (single controlled change).

## Steps
1. Load the frozen train/validation/test split. Do not re-split.
2. Data audit first: label taxonomy, duplicate/near-duplicate texts across splits,
   leakage (no target/future info in features).
3. Fit TF-IDF on **train only**; fit Logistic Regression with balanced class weights.
4. Evaluate on the **validation** set: macro_f1, per-class recall, confusion matrix.
   Keep the **test set untouched** until final validation.
5. Record the seed and the split file paths.

## Guardrails (from context)
- Baseline before main model; one controlled change per experiment.
- Stratified split, frozen before model comparison.
- No tuning on the test set.

## Next step (do not skip)
```bash
octopus exp ingest --run-dir runs/baseline_tfidf_logreg --kind baseline
octopus exp profile
```
Stop here; do not start PhoBERT until the baseline is ingested/logged.
