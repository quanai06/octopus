from datetime import UTC, datetime
from pathlib import Path

from octopus.core.files import atomic_write_text
from octopus.core.paths import (
    BEST_RUNS_MD,
    DECISIONS_MD,
    EXPERIMENT_MEMORY_MD,
    FAILURES_MD,
    REPORTS_DIR,
)
from octopus.core.schemas import DiagnosisSignal, ExperimentDiagnosis, ExperimentRecord
from octopus.storage.experiment_store import list_experiments, load_experiment, save_experiment
from octopus.storage.state_store import load_state, state_exists

LOW_METRIC_THRESHOLD = 0.55
LOW_RECALL_THRESHOLD = 0.60


def analyze_experiment(experiment_id: str) -> ExperimentDiagnosis:
    record = load_experiment(experiment_id)
    history = list_experiments()
    main_metric = _main_metric(history)
    main_value = record.metrics.get(main_metric)
    baseline = _best_baseline(history, main_metric)
    best_previous = _best_previous(history, record, main_metric)
    target_score = _target_score()
    baseline_delta = _delta(main_value, baseline.metrics.get(main_metric) if baseline else None)
    best_value = best_previous.metrics.get(main_metric) if best_previous else None
    best_delta = _delta(main_value, best_value)
    target_gap = _delta(target_score, main_value)

    signals = [
        detect_overfitting(record, history),
        detect_underfitting(record, history),
        detect_imbalance(record, history),
        detect_metric_gap(record, history),
        detect_unstable_training(record, history),
    ]
    detected = [signal for signal in signals if signal.status == "detected"]
    recommended_focus = _recommended_focus(detected, target_gap)
    summary = _summary(record, main_metric, main_value, detected, target_gap)
    evidence = _evidence(record, main_metric, baseline, best_previous, target_score)
    for signal in detected:
        evidence.extend(signal.evidence)

    diagnosis = ExperimentDiagnosis(
        experiment_id=record.experiment_id or record.id,
        main_metric=main_metric,
        main_metric_value=main_value,
        baseline_delta=baseline_delta,
        best_delta=best_delta,
        target_gap=target_gap,
        signals=signals,
        evidence=evidence,
        summary=summary,
        recommended_focus=recommended_focus,
    )

    report_path = write_training_review(record, diagnosis, baseline, best_previous)
    record.diagnosis_id = report_path.stem
    save_experiment(record, allow_overwrite=True)
    write_memory_markdown(history=list_experiments(), main_metric=main_metric)
    return diagnosis


def detect_overfitting(
    record: ExperimentRecord, history: list[ExperimentRecord]
) -> DiagnosisSignal:
    train_loss = record.metrics.get("train_loss")
    val_loss = record.metrics.get("val_loss") or record.metrics.get("validation_loss")
    note = " ".join(record.notes).lower()
    evidence: list[str] = []
    if train_loss is not None:
        evidence.append(f"train_loss={train_loss:g}")
    if val_loss is not None:
        evidence.append(f"val_loss={val_loss:g}")
    if "overfit" in note:
        evidence.append("notes mention overfitting")
    detected = (
        (train_loss is not None and val_loss is not None and val_loss > train_loss * 1.4)
        or "overfit" in note
    )
    return DiagnosisSignal(
        name="overfitting",
        status="detected" if detected else "not_detected",
        confidence="high" if detected and len(evidence) >= 2 else "medium",
        evidence=evidence,
    )


def detect_underfitting(
    record: ExperimentRecord, history: list[ExperimentRecord]
) -> DiagnosisSignal:
    train_loss = record.metrics.get("train_loss")
    val_loss = record.metrics.get("val_loss") or record.metrics.get("validation_loss")
    main_metric = _main_metric(history)
    main_value = record.metrics.get(main_metric)
    evidence: list[str] = []
    if train_loss is not None:
        evidence.append(f"train_loss={train_loss:g}")
    if val_loss is not None:
        evidence.append(f"val_loss={val_loss:g}")
    if main_value is not None:
        evidence.append(f"{main_metric}={main_value:g}")
    detected = (
        train_loss is not None
        and val_loss is not None
        and train_loss > 1.0
        and val_loss > 1.0
        and (main_value is None or main_value < LOW_METRIC_THRESHOLD)
    )
    return DiagnosisSignal(
        name="underfitting",
        status="detected" if detected else "not_detected",
        confidence="medium",
        evidence=evidence,
    )


def detect_imbalance(record: ExperimentRecord, history: list[ExperimentRecord]) -> DiagnosisSignal:
    evidence: list[str] = []
    low_recalls = [
        f"{label}.recall={metrics.recall:g}"
        for label, metrics in record.per_class.items()
        if metrics.recall is not None and metrics.recall < LOW_RECALL_THRESHOLD
    ]
    supports = [
        metrics.support
        for metrics in record.per_class.values()
        if metrics.support is not None and metrics.support > 0
    ]
    metric_recalls = [
        f"{key}={value:g}"
        for key, value in record.metrics.items()
        if "recall" in key.lower() and value < LOW_RECALL_THRESHOLD
    ]
    evidence.extend(low_recalls[:5])
    evidence.extend(metric_recalls[:5])
    if supports:
        support_min = min(supports)
        support_max = max(supports)
        evidence.append(f"support range={support_min}..{support_max}")
    detected = bool(low_recalls or metric_recalls) or (
        bool(supports) and min(supports) > 0 and max(supports) / min(supports) >= 3
    )
    return DiagnosisSignal(
        name="class_imbalance",
        status="detected" if detected else "not_detected",
        confidence="high" if low_recalls else "medium",
        evidence=evidence,
    )


def detect_metric_gap(record: ExperimentRecord, history: list[ExperimentRecord]) -> DiagnosisSignal:
    accuracy = record.metrics.get("accuracy")
    macro_f1 = record.metrics.get("macro_f1") or record.metrics.get("macro_f1_score")
    evidence: list[str] = []
    if accuracy is not None:
        evidence.append(f"accuracy={accuracy:g}")
    if macro_f1 is not None:
        evidence.append(f"macro_f1={macro_f1:g}")
    detected = accuracy is not None and macro_f1 is not None and accuracy - macro_f1 >= 0.10
    return DiagnosisSignal(
        name="metric_gap",
        status="detected" if detected else "not_detected",
        confidence="high" if detected else "medium",
        evidence=evidence,
    )


def detect_unstable_training(
    record: ExperimentRecord, history: list[ExperimentRecord]
) -> DiagnosisSignal:
    note = " ".join(record.notes).lower()
    evidence: list[str] = []
    loss_std = record.metrics.get("loss_std")
    if loss_std is not None:
        evidence.append(f"loss_std={loss_std:g}")
    if any(token in note for token in ("unstable", "diverge", "diverged", "nan", "inf")):
        evidence.append("notes mention unstable training")
    detected = (loss_std is not None and loss_std > 0.2) or bool(evidence and loss_std is None)
    return DiagnosisSignal(
        name="unstable_training",
        status="detected" if detected else "not_detected",
        confidence="medium",
        evidence=evidence,
    )


def write_training_review(
    record: ExperimentRecord,
    diagnosis: ExperimentDiagnosis,
    baseline: ExperimentRecord | None,
    best_previous: ExperimentRecord | None,
) -> Path:
    report_path = REPORTS_DIR / f"training_review_{record.experiment_id or record.id}.md"
    detected = [signal for signal in diagnosis.signals if signal.status == "detected"]
    lines = [
        f"# Training Review - {record.experiment_id or record.id}",
        "",
        "## 1. Run Summary",
        "",
        f"- Name: {record.name}",
        f"- Kind: {record.kind}",
        f"- Model: {record.model or 'not specified'}",
        f"- Dataset: {record.dataset or 'not specified'}",
        f"- Status: {record.status}",
        f"- Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        "",
        "## 2. Metrics",
        "",
        *_bullet_metrics(record.metrics),
        "",
        "## 3. Comparison",
        "",
        f"- Baseline: {_record_metric_text(baseline, diagnosis.main_metric)}",
        f"- Best previous: {_record_metric_text(best_previous, diagnosis.main_metric)}",
        f"- Delta vs baseline: {_format_delta(diagnosis.baseline_delta)}",
        f"- Delta vs best previous: {_format_delta(diagnosis.best_delta)}",
        f"- Target gap: {_format_delta(diagnosis.target_gap)}",
        "",
        "## 4. Diagnosis",
        "",
        diagnosis.summary,
        "",
        "## 5. Evidence",
        "",
        *_bullet_list(diagnosis.evidence),
        "",
        "## 6. What Likely Happened",
        "",
        _likely_happened(detected),
        "",
        "## 7. Recommended Focus",
        "",
        *_bullet_list(diagnosis.recommended_focus),
        "",
        "## 8. Guardrails",
        "",
        "- Do not tune on the test set.",
        "- Do not change train/validation/test split unless this is the selected direction.",
        "- Implement one controlled change before the next experiment.",
        "- Ingest the next run with `octopus exp ingest --run-dir <run_dir>`.",
        "",
    ]
    atomic_write_text(report_path, "\n".join(lines))
    return report_path


def write_memory_markdown(*, history: list[ExperimentRecord], main_metric: str) -> None:
    completed = [record for record in history if record.status == "completed"]
    best = _best_by_metric(completed, main_metric)
    atomic_write_text(EXPERIMENT_MEMORY_MD, _render_experiment_memory(history, main_metric))
    atomic_write_text(BEST_RUNS_MD, _render_best_runs(best, completed, main_metric))
    if not FAILURES_MD.exists():
        atomic_write_text(
            FAILURES_MD,
            "# Failure Memory\n\n## Failed Directions\n\n_No failed directions recorded yet._\n",
        )
    if not DECISIONS_MD.exists():
        atomic_write_text(
            DECISIONS_MD,
            "# Decision Memory\n\n_No selected experiment decisions recorded yet._\n",
        )


def _main_metric(records: list[ExperimentRecord]) -> str:
    if state_exists():
        try:
            state = load_state()
            if state.main_metric:
                return state.main_metric
        except FileNotFoundError:
            pass
    for preferred in ("macro_f1", "accuracy", "f1", "rmse", "mae"):
        if any(preferred in record.metrics for record in records):
            return preferred
    for record in records:
        if record.metrics:
            return next(iter(record.metrics))
    return "macro_f1"


def _target_score() -> float | None:
    if not state_exists():
        return None
    try:
        return load_state().target_score
    except FileNotFoundError:
        return None


def _best_baseline(records: list[ExperimentRecord], metric: str) -> ExperimentRecord | None:
    baselines = [
        record
        for record in records
        if record.kind == "baseline" and record.status == "completed"
    ]
    return _best_by_metric(
        baselines,
        metric,
    )


def _best_previous(
    records: list[ExperimentRecord], target: ExperimentRecord, metric: str
) -> ExperimentRecord | None:
    target_id = target.experiment_id or target.id
    previous = [
        record
        for record in records
        if (record.experiment_id or record.id) != target_id
        and record.status == "completed"
        and metric in record.metrics
    ]
    return _best_by_metric(previous, metric)


def _best_by_metric(records: list[ExperimentRecord], metric: str) -> ExperimentRecord | None:
    candidates = [record for record in records if metric in record.metrics]
    return max(candidates, key=lambda record: record.metrics[metric]) if candidates else None


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _evidence(
    record: ExperimentRecord,
    main_metric: str,
    baseline: ExperimentRecord | None,
    best_previous: ExperimentRecord | None,
    target_score: float | None,
) -> list[str]:
    items = [f"{key}={value:g}" for key, value in record.metrics.items()]
    if record.artifacts.metrics_path:
        items.append(f"metrics source: {record.artifacts.metrics_path}")
    if record.artifacts.report_path:
        items.append(f"classification report source: {record.artifacts.report_path}")
    if baseline and main_metric in baseline.metrics:
        items.append(f"baseline {baseline.id} {main_metric}={baseline.metrics[main_metric]:g}")
    if best_previous and main_metric in best_previous.metrics:
        items.append(
            f"best previous {best_previous.id} {main_metric}={best_previous.metrics[main_metric]:g}"
        )
    if target_score is not None:
        items.append(f"target {main_metric}={target_score:g}")
    return items or ["No structured metrics were available."]


def _recommended_focus(
    detected: list[DiagnosisSignal], target_gap: float | None
) -> list[str]:
    names = {signal.name for signal in detected}
    focus: list[str] = []
    if "class_imbalance" in names or "metric_gap" in names:
        focus.append("Prioritize macro F1 and per-class recall over accuracy-only changes.")
        focus.append("Try class weights, weighted sampling, focal loss, or minority sample review.")
    if "overfitting" in names:
        focus.append("Add early stopping, weight decay/dropout, or reduce epochs.")
    if "underfitting" in names:
        focus.append("Check preprocessing, features, model capacity, and learning-rate schedule.")
    if "unstable_training" in names:
        focus.append(
            "Lower learning rate, add gradient clipping, and inspect batch/mixed precision."
        )
    if target_gap is not None and target_gap > 0 and target_gap <= 0.03:
        focus.append("Target gap is small; prefer low-risk controlled changes.")
    return focus or ["Run one controlled experiment and compare against the current best run."]


def _summary(
    record: ExperimentRecord,
    main_metric: str,
    main_value: float | None,
    detected: list[DiagnosisSignal],
    target_gap: float | None,
) -> str:
    metric_text = f"{main_metric}={main_value:g}" if main_value is not None else "no main metric"
    if detected:
        names = ", ".join(signal.name for signal in detected)
        return f"{record.id} reached {metric_text}; detected signals: {names}."
    if target_gap is not None and target_gap > 0:
        return f"{record.id} reached {metric_text}; no strong failure signal, target gap remains."
    return f"{record.id} reached {metric_text}; no strong failure signal detected."


def _likely_happened(detected: list[DiagnosisSignal]) -> str:
    names = {signal.name for signal in detected}
    if "class_imbalance" in names or "metric_gap" in names:
        return (
            "The model likely performs unevenly across classes, so aggregate accuracy "
            "hides minority-class errors."
        )
    if "overfitting" in names:
        return "The model likely fit the training set faster than validation quality improved."
    if "underfitting" in names:
        return (
            "The model likely has insufficient signal, capacity, training, or a "
            "preprocessing issue."
        )
    if "unstable_training" in names:
        return "The optimization setup likely produced noisy or divergent validation behavior."
    return "The available structured evidence does not support a single strong diagnosis yet."


def _record_metric_text(record: ExperimentRecord | None, metric: str | None) -> str:
    if not record:
        return "not available"
    if metric and metric in record.metrics:
        return f"{record.id} ({record.name}) {metric}={record.metrics[metric]:g}"
    return f"{record.id} ({record.name})"


def _bullet_metrics(metrics: dict[str, float]) -> list[str]:
    return _bullet_list([f"{key}: {value:g}" for key, value in metrics.items()] or ["No metrics."])


def _bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None."]


def _format_delta(value: float | None) -> str:
    return "not available" if value is None else f"{value:+.3f}"


def _render_experiment_memory(records: list[ExperimentRecord], main_metric: str) -> str:
    lines = ["# Experiment Memory", ""]
    if not records:
        lines.append("_No experiments recorded yet._")
    for record in records:
        lines.extend(
            [
                f"## {record.id} - {record.name}",
                f"- Kind: {record.kind}",
                f"- Status: {record.status}",
                f"- Model: {record.model or 'not specified'}",
                f"- Main metric: {main_metric} = {_metric_value(record, main_metric)}",
            ]
        )
        if record.notes:
            lines.append(f"- Notes: {'; '.join(record.notes[:3])}")
        lines.append("")
    return "\n".join(lines)


def _render_best_runs(
    best: ExperimentRecord | None, completed: list[ExperimentRecord], main_metric: str
) -> str:
    lines = ["# Best Runs", ""]
    if best:
        lines.extend(
            [
                f"- Best experiment: {best.id}",
                f"- Name: {best.name}",
                f"- {main_metric}: {best.metrics.get(main_metric):g}",
                "",
            ]
        )
    else:
        lines.extend(["_No completed best run yet._", ""])
    lines.extend(["## Completed Runs", ""])
    for record in completed:
        lines.append(f"- {record.id}: {main_metric}={_metric_value(record, main_metric)}")
    return "\n".join(lines)


def _metric_value(record: ExperimentRecord, metric: str) -> str:
    value = record.metrics.get(metric)
    return "not available" if value is None else f"{value:g}"
