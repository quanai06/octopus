from dataclasses import dataclass

from octopus.core.schemas import ExperimentRecord

LOW_METRIC_THRESHOLD = 0.55
LOW_RECALL_THRESHOLD = 0.6
UNCHANGED_DELTA = 0.01

LOSS_KEYS = {"loss", "train_loss", "val_loss", "validation_loss"}
NON_PERFORMANCE_KEYWORDS = ("loss", "time", "latency", "memory", "epoch")
MINORITY_HINTS = ("minority", "recall", "fear", "rare", "class")


@dataclass(frozen=True)
class ExperimentDiagnosis:
    pattern: str
    likely_cause: str
    evidence: list[str]
    actions: list[str]


def suggest_for_experiment(record: ExperimentRecord) -> list[str]:
    ideas: list[str] = []
    note = " ".join(record.notes).lower()
    metrics = record.metrics

    if _looks_overfit(metrics, note):
        ideas.extend(
            [
                "add early stopping",
                "try lower learning rate",
                "increase regularization or reduce epochs",
            ]
        )

    if _minority_recall_low(metrics):
        ideas.extend(
            [
                "try class weights or balanced sampling",
                "inspect minority-class label noise",
            ]
        )

    if _all_performance_metrics_low(metrics):
        ideas.extend(
            [
                "check baseline implementation and data preprocessing",
                "inspect dataset split and label quality",
            ]
        )

    if _loss_unstable(metrics, note):
        ideas.extend(
            [
                "lower the learning rate",
                "check gradient clipping and batch size",
            ]
        )

    return _dedupe(ideas)


def suggest_from_history(records: list[ExperimentRecord]) -> list[str]:
    if not records:
        return ["log at least one experiment before requesting suggestions"]

    ideas = suggest_for_experiment(records[-1])
    unchanged = _unchanged_metric(records)
    if unchanged:
        ideas.append(
            f"{unchanged} has barely changed across recent experiments; inspect labels and split"
        )

    if len(records) >= 3 and not ideas:
        ideas.append("review error cases before adding more model complexity")

    return _dedupe(ideas) or ["no obvious issue found; run the next controlled experiment"]


def diagnose_experiment(record: ExperimentRecord) -> ExperimentDiagnosis:
    metrics = record.metrics
    note = " ".join(record.notes).lower()
    evidence = _metric_evidence(metrics)

    if _accuracy_macro_gap(metrics):
        return ExperimentDiagnosis(
            pattern="Accuracy is high but macro F1 is much lower.",
            likely_cause=(
                "The dataset may be imbalanced. The model is likely performing well "
                "on majority classes while missing minority classes."
            ),
            evidence=evidence,
            actions=[
                "Check class distribution.",
                "Use class weights, focal loss, or balanced sampling.",
                "Inspect minority class labels.",
                "Track per-class recall instead of accuracy only.",
            ],
        )

    if _minority_recall_low(metrics):
        return ExperimentDiagnosis(
            pattern="Minority recall is low.",
            likely_cause="Class imbalance, label noise, or insufficient minority examples.",
            evidence=evidence,
            actions=[
                "Inspect minority examples manually.",
                "Try class weights or balanced sampling.",
                "Review confusion matrix for systematic confusion.",
                "Collect or clean minority-class samples if labels are noisy.",
            ],
        )

    train_loss = metrics.get("train_loss")
    val_loss = metrics.get("val_loss") or metrics.get("validation_loss")
    if _looks_overfit(metrics, note):
        return ExperimentDiagnosis(
            pattern="Training loss improves while validation quality degrades.",
            likely_cause="The model is overfitting the training data.",
            evidence=evidence,
            actions=[
                "Add early stopping.",
                "Try lower learning rate.",
                "Reduce epochs or increase regularization.",
                "Inspect train/validation distribution mismatch.",
            ],
        )

    if train_loss is not None and val_loss is not None and train_loss > 1.0 and val_loss > 1.0:
        return ExperimentDiagnosis(
            pattern="Training loss and validation loss are both high.",
            likely_cause="The model may be underfitting or the input pipeline is broken.",
            evidence=evidence,
            actions=[
                "Check preprocessing and labels.",
                "Run a small overfit-on-one-batch test.",
                "Try stronger baseline features or more model capacity.",
            ],
        )

    if _loss_unstable(metrics, note):
        return ExperimentDiagnosis(
            pattern="Loss appears unstable.",
            likely_cause="Learning rate may be too high or batches are too noisy.",
            evidence=evidence,
            actions=[
                "Lower learning rate.",
                "Enable gradient clipping.",
                "Check batch size and mixed precision settings.",
            ],
        )

    if _all_performance_metrics_low(metrics):
        return ExperimentDiagnosis(
            pattern="All tracked performance metrics are low.",
            likely_cause="Baseline, labels, split, or preprocessing may be flawed.",
            evidence=evidence,
            actions=[
                "Validate dataset split.",
                "Inspect labels and examples.",
                "Confirm baseline implementation.",
                "Run a simpler sanity-check model.",
            ],
        )

    return ExperimentDiagnosis(
        pattern="No strong failure pattern detected.",
        likely_cause="The experiment needs more evidence or targeted error analysis.",
        evidence=evidence or ["No metrics were logged."],
        actions=[
            "Inspect error cases.",
            "Compare against baseline and previous best experiment.",
            "Run one controlled change in the next experiment.",
        ],
    )


def _looks_overfit(metrics: dict[str, float], note: str) -> bool:
    if "overfit" in note or "overfitting" in note:
        return True
    train_loss = metrics.get("train_loss")
    val_loss = metrics.get("val_loss") or metrics.get("validation_loss")
    return train_loss is not None and val_loss is not None and val_loss > train_loss * 1.4


def _accuracy_macro_gap(metrics: dict[str, float]) -> bool:
    accuracy = metrics.get("accuracy")
    macro_f1 = metrics.get("macro_f1") or metrics.get("macro_f1_score")
    return accuracy is not None and macro_f1 is not None and accuracy - macro_f1 >= 0.15


def _minority_recall_low(metrics: dict[str, float]) -> bool:
    for key, value in metrics.items():
        normalized = key.lower()
        if "recall" in normalized and value < LOW_RECALL_THRESHOLD:
            return True
        if any(hint in normalized for hint in MINORITY_HINTS) and value < LOW_RECALL_THRESHOLD:
            return True
    return False


def _performance_metrics(metrics: dict[str, float]) -> dict[str, float]:
    return {
        key: value
        for key, value in metrics.items()
        if not any(keyword in key.lower() for keyword in NON_PERFORMANCE_KEYWORDS)
    }


def _all_performance_metrics_low(metrics: dict[str, float]) -> bool:
    performance = _performance_metrics(metrics)
    return bool(performance) and all(value < LOW_METRIC_THRESHOLD for value in performance.values())


def _loss_unstable(metrics: dict[str, float], note: str) -> bool:
    if any(marker in note for marker in ("unstable", "diverge", "diverged", "nan loss")):
        return True
    return metrics.get("loss_std", 0.0) > 0.2


def _metric_evidence(metrics: dict[str, float]) -> list[str]:
    return [f"{key}: {value:g}" for key, value in metrics.items()]


def _unchanged_metric(records: list[ExperimentRecord]) -> str | None:
    recent = records[-3:]
    common_keys = set(recent[0].metrics)
    for record in recent[1:]:
        common_keys &= set(record.metrics)
    candidates = [
        key
        for key in common_keys
        if key not in LOSS_KEYS and not any(token in key.lower() for token in ("time", "latency"))
    ]
    for key in sorted(candidates):
        values = [record.metrics[key] for record in recent]
        if max(values) - min(values) <= UNCHANGED_DELTA:
            return key
    return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
