from octopus.core.schemas import ExperimentRecord, ProjectState
from octopus.planners.experiment_advisor import diagnose_experiment, suggest_from_history


def render_experiment_report(state: ProjectState, records: list[ExperimentRecord]) -> str:
    completed = [record for record in records if record.status == "completed"]
    metric = state.main_metric or _first_metric(completed) or "primary_metric"
    best = _best_by_metric(completed, metric)
    baseline = completed[0] if completed else None
    suggestions = suggest_from_history(completed)

    lines = [
        "# Experiment Report",
        "",
        "## Project Goal",
        "",
        state.project_goal or "_Not specified._",
        "",
        "## Dataset Summary",
        "",
        f"- Status: {state.dataset_status or 'unknown'}",
        f"- Size: {state.dataset_size_note or 'not specified'}",
        f"- Labels: {_labels_text(state.has_labels)}",
        f"- Class imbalance: {_imbalance_text(state.has_class_imbalance)}",
        "",
        "## Baseline",
        "",
    ]

    if baseline:
        lines.extend(
            [
                f"- {baseline.id}: {baseline.name}",
                f"- Model: {baseline.model or 'not specified'}",
                f"- Metrics: {_format_metrics(baseline.metrics)}",
            ]
        )
    else:
        lines.append("_No completed baseline logged yet._")

    lines.extend(["", "## Experiment Timeline", ""])
    if completed:
        lines.extend(
            [
                "| Exp | Model | Metrics | Note |",
                "|---|---|---|---|",
            ]
        )
        for record in completed:
            lines.append(
                "| "
                f"{record.id} | "
                f"{record.model or '-'} | "
                f"{_format_metrics(record.metrics)} | "
                f"{'; '.join(record.notes) or '-'} |"
            )
    else:
        lines.append("_No completed experiments yet._")

    lines.extend(["", "## Best Result", ""])
    if best:
        lines.extend(
            [
                f"- Experiment: {best.id} ({best.name})",
                f"- Model: {best.model or 'not specified'}",
                f"- {metric}: {best.metrics[metric]:g}",
            ]
        )
        if baseline and metric in baseline.metrics and best.id != baseline.id:
            delta = best.metrics[metric] - baseline.metrics[metric]
            lines.append(f"- Improvement over baseline: {delta:+.3f}")
    else:
        lines.append(f"_No experiment has metric `{metric}` yet._")

    lines.extend(["", "## Failure Patterns", ""])
    patterns = _failure_patterns(completed)
    if patterns:
        for pattern in patterns:
            lines.append(f"- {pattern}")
    else:
        lines.append("_No strong repeated failure pattern detected yet._")

    lines.extend(["", "## Lessons Learned", ""])
    lessons = [note for record in completed for note in record.notes]
    if lessons:
        for note in lessons[-8:]:
            lines.append(f"- {note}")
    else:
        lines.append("_No experiment notes logged yet._")

    lines.extend(["", "## Next Plan", ""])
    for suggestion in suggestions:
        lines.append(f"- {suggestion}")
    lines.append("")
    return "\n".join(lines)


def _first_metric(records: list[ExperimentRecord]) -> str | None:
    for record in records:
        if record.metrics:
            return next(iter(record.metrics))
    return None


def _best_by_metric(records: list[ExperimentRecord], metric: str) -> ExperimentRecord | None:
    candidates = [record for record in records if metric in record.metrics]
    if not candidates:
        return None
    return max(candidates, key=lambda record: record.metrics[metric])


def _failure_patterns(records: list[ExperimentRecord]) -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()
    for record in records:
        diagnosis = diagnose_experiment(record)
        if diagnosis.pattern == "No strong failure pattern detected.":
            continue
        if diagnosis.pattern in seen:
            continue
        seen.add(diagnosis.pattern)
        patterns.append(diagnosis.pattern)
    return patterns


def _format_metrics(metrics: dict[str, float]) -> str:
    if not metrics:
        return "-"
    return ", ".join(f"{key}={value:g}" for key, value in metrics.items())


def _labels_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "available" if value else "not available"


def _imbalance_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"
