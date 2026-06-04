from datetime import UTC, datetime
from typing import Annotated, Literal, cast

import typer
from rich.console import Console
from rich.table import Table

from octopus.core.files import atomic_write_text
from octopus.core.guards import require_init
from octopus.core.paths import EXPERIMENT_REPORT_MD, TASKS_MD
from octopus.core.schemas import ExperimentRecord
from octopus.core.workflow import (
    has_completed_baseline,
    infer_experiment_kind,
    requires_baseline_gate,
)
from octopus.planners.experiment_advisor import (
    diagnose_experiment,
    suggest_for_experiment,
    suggest_from_history,
)
from octopus.planners.experiment_report import render_experiment_report
from octopus.storage.experiment_store import (
    get_experiment,
    initialize_experiment_tracking,
    latest_experiment,
    list_experiments,
    next_experiment_id,
    save_experiment,
)
from octopus.storage.state_store import load_state, state_exists
from octopus.storage.task_store import ensure_tasks, mark_baseline_tasks_done, render_tasks_markdown

app = typer.Typer(help="Log and inspect ML experiments.")
console = Console()
ExperimentStatus = Literal["planned", "running", "completed", "failed", "skipped"]
ExperimentKind = Literal["baseline", "candidate", "main", "other"]


@app.command("init")
def init_experiment_tracking() -> None:
    require_init()
    created = initialize_experiment_tracking(create_placeholder=True)
    console.print("[green]Experiment tracking initialized.[/green]\n")
    for path in created:
        console.print(f"  {path.as_posix()}")


@app.command("log")
def log_experiment(
    name: Annotated[str, typer.Option("--name", help="Experiment name.")],
    kind: Annotated[
        str,
        typer.Option(
            "--kind",
            help="Experiment kind: auto, baseline, candidate, main, or other.",
        ),
    ] = "auto",
    metric: Annotated[
        list[str] | None,
        typer.Option("--metric", help="Metric in key=value form. Can be repeated."),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Model name.")] = None,
    dataset: Annotated[str | None, typer.Option("--dataset", help="Dataset name.")] = None,
    note: Annotated[
        str | None,
        typer.Option("--note", help="Experiment observation note."),
    ] = None,
    status: Annotated[
        str,
        typer.Option("--status", help="planned, running, completed, failed, or skipped."),
    ] = "completed",
) -> None:
    require_init()
    if kind not in {"auto", "baseline", "candidate", "main", "other"}:
        console.print("[red]Invalid experiment kind.[/red]")
        console.print("Use: auto, baseline, candidate, main, or other.")
        raise typer.Exit(1)
    if status not in {"planned", "running", "completed", "failed", "skipped"}:
        console.print("[red]Invalid status.[/red]")
        console.print("Use: planned, running, completed, failed, or skipped.")
        raise typer.Exit(1)
    status_value = cast(ExperimentStatus, status)
    kind_value = cast(ExperimentKind, infer_experiment_kind(name, model, kind))
    if state_exists():
        state = load_state()
        if (
            requires_baseline_gate(state)
            and kind_value in {"candidate", "main"}
            and not has_completed_baseline()
        ):
            console.print("[red]Main model experiment blocked: no completed baseline found.[/red]")
            console.print("Start with a baseline and log it first:")
            console.print(
                "  octopus exp log --kind baseline --name baseline --metric "
                f"{state.main_metric or 'metric'}=<value>"
            )
            console.print("Then run: octopus task start T020")
            raise typer.Exit(1)
    metrics = _parse_metrics(metric or [])
    notes = _parse_notes(note)
    record = ExperimentRecord(
        id=next_experiment_id(),
        name=name,
        kind=kind_value,
        model=model,
        dataset=dataset,
        metrics=metrics,
        notes=notes,
        status=status_value,
        created_at=datetime.now(UTC),
    )
    record.next_ideas = suggest_for_experiment(record)
    path = save_experiment(record)
    if state_exists() and kind_value == "baseline" and status_value == "completed":
        state = load_state()
        tasks = mark_baseline_tasks_done(ensure_tasks(state))
        atomic_write_text(TASKS_MD, render_tasks_markdown(state, tasks))

    console.print("[green]Experiment logged.[/green]\n")
    console.print(f"  ID:     {record.id}")
    console.print(f"  Name:   {record.name}")
    console.print(f"  Kind:   {record.kind}")
    console.print(f"  Output: {path.as_posix()}")
    if record.next_ideas:
        console.print("\n  Next ideas:")
        for idea in record.next_ideas:
            console.print(f"    - {idea}")


@app.command("list")
def list_logged_experiments() -> None:
    require_init()
    records = list_experiments()
    if not records:
        console.print("No experiments logged yet.")
        return

    table = Table(title="Octopus Experiments")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Main Metrics")
    table.add_column("Ideas")
    for record in records:
        table.add_row(
            record.id,
            record.name,
            record.model or "-",
            record.status,
            _format_metrics(record.metrics),
            str(len(record.next_ideas)),
        )
    console.print(table)


@app.command("compare")
def compare_experiments(
    metric: Annotated[
        str | None,
        typer.Option("--metric", help="Metric to rank by. Defaults to project main metric."),
    ] = None,
) -> None:
    require_init()
    records = [record for record in list_experiments() if record.status == "completed"]
    if not records:
        console.print("No completed experiments to compare.")
        return

    main_metric = metric or _default_metric(records)
    best = _best_by_metric(records, main_metric)
    baseline = _first_with_metric(records, main_metric)

    if best:
        console.print(f"[bold]Best experiment by {main_metric}:[/bold]")
        console.print(f"- {best.id}: {best.name}")
        console.print(f"- {main_metric}: {best.metrics[main_metric]:g}")
        if baseline and baseline.id != best.id:
            delta = best.metrics[main_metric] - baseline.metrics[main_metric]
            console.print(f"- improvement over baseline: {delta:+.3f}")
        console.print("")
    else:
        console.print(f"No completed experiment has metric '{main_metric}'.\n")

    table = Table(title="Experiment Comparison")
    table.add_column("Exp")
    table.add_column("Model")
    for key in _metric_columns(records, preferred=main_metric):
        table.add_column(key)
    table.add_column("Note")
    for record in records:
        metric_columns = _metric_columns(records, preferred=main_metric)
        row = [
            record.id,
            record.model or "-",
            *[_metric_value(record.metrics, key) for key in metric_columns],
            "; ".join(record.notes[:1]) or "-",
        ]
        table.add_row(*row)
    console.print(table)

    warnings = _comparison_warnings(records)
    if warnings:
        console.print("\n[bold yellow]Warning:[/bold yellow]")
        for warning in warnings:
            console.print(f"- {warning}")


@app.command("diagnose")
def diagnose_logged_experiment(
    exp_id: Annotated[
        str | None,
        typer.Option("--exp", help="Experiment ID. Defaults to latest experiment."),
    ] = None,
) -> None:
    require_init()
    try:
        record = get_experiment(exp_id) if exp_id else latest_experiment()
    except FileNotFoundError as exc:
        console.print(f"[red]Experiment not found: {exc.filename}[/red]")
        raise typer.Exit(1) from exc
    if record is None:
        console.print("No experiments logged yet.")
        return

    diagnosis = diagnose_experiment(record)
    console.print("# Experiment Diagnosis\n")
    console.print("## Detected Pattern")
    console.print(diagnosis.pattern)
    console.print("\n## Likely Cause")
    console.print(diagnosis.likely_cause)
    console.print("\n## Evidence")
    for item in diagnosis.evidence:
        console.print(f"- {item}")
    console.print("\n## Recommended Actions")
    for index, action in enumerate(diagnosis.actions, start=1):
        console.print(f"{index}. {action}")


@app.command("suggest")
def suggest_next_experiment() -> None:
    require_init()
    records = list_experiments()
    completed = [record for record in records if record.status == "completed"]
    ideas = suggest_from_history(completed)
    latest = completed[-1] if completed else None
    diagnosis = diagnose_experiment(latest) if latest else None

    console.print("# Next Experiment Suggestion\n")
    console.print("## Recommended Next Step")
    console.print(_recommended_step(latest, ideas))
    console.print("\n## Why")
    console.print(diagnosis.likely_cause if diagnosis else "No completed experiment is logged yet.")
    console.print("\n## Suggested Config")
    for line in _suggested_config(latest):
        console.print(f"- {line}")
    console.print("\n## Do Not Try Yet")
    for item in _do_not_try_yet(diagnosis.pattern if diagnosis else ""):
        console.print(f"- {item}")
    console.print("\n## Rule-Based Ideas")
    for idea in ideas:
        console.print(f"- {idea}")


@app.command("report")
def write_experiment_report() -> None:
    require_init()
    if not state_exists():
        console.print("[red]Project state not found.[/red]")
        console.print("Run: [bold]octopus ask[/bold]")
        raise typer.Exit(1)
    records = list_experiments()
    content = render_experiment_report(load_state(), records)
    atomic_write_text(EXPERIMENT_REPORT_MD, content)
    console.print("[green]Experiment report generated.[/green]\n")
    console.print(f"  Output: {EXPERIMENT_REPORT_MD.as_posix()}")


def _parse_metrics(values: list[str]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for value in values:
        if "=" not in value:
            console.print(f"[red]Invalid metric '{value}'. Use key=value.[/red]")
            raise typer.Exit(1)
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            console.print(f"[red]Invalid metric '{value}'. Metric key is empty.[/red]")
            raise typer.Exit(1)
        try:
            metrics[key] = float(raw)
        except ValueError as exc:
            console.print(f"[red]Invalid metric value '{raw}' for {key}.[/red]")
            raise typer.Exit(1) from exc
    return metrics


def _parse_notes(note: str | None) -> list[str]:
    if not note:
        return []
    normalized = note.replace(" but ", ". ").replace(" and ", ". ")
    parts = [
        part.strip(" .") for part in normalized.replace(";", ".").split(".") if part.strip(" .")
    ]
    return parts or [note.strip()]


def _format_metrics(metrics: dict[str, float]) -> str:
    if not metrics:
        return "-"
    return ", ".join(f"{key}={value:g}" for key, value in list(metrics.items())[:3])


def _default_metric(records: list[ExperimentRecord]) -> str:
    if state_exists():
        state = load_state()
        if state.main_metric:
            return state.main_metric
    for preferred in ("macro_f1", "accuracy", "f1", "rmse", "mae"):
        if any(preferred in record.metrics for record in records):
            return preferred
    return next(iter(records[0].metrics), "macro_f1")


def _best_by_metric(records: list[ExperimentRecord], metric: str) -> ExperimentRecord | None:
    candidates = [record for record in records if metric in record.metrics]
    if not candidates:
        return None
    return max(candidates, key=lambda record: record.metrics[metric])


def _first_with_metric(records: list[ExperimentRecord], metric: str) -> ExperimentRecord | None:
    return next((record for record in records if metric in record.metrics), None)


def _metric_columns(records: list[ExperimentRecord], *, preferred: str) -> list[str]:
    keys = [preferred]
    for record in records:
        for key in record.metrics:
            if key not in keys:
                keys.append(key)
    return keys[:5]


def _metric_value(metrics: dict[str, float], key: str) -> str:
    if key not in metrics:
        return "-"
    return f"{metrics[key]:g}"


def _comparison_warnings(records: list[ExperimentRecord]) -> list[str]:
    warnings: list[str] = []
    for record in records:
        accuracy = record.metrics.get("accuracy")
        macro_f1 = record.metrics.get("macro_f1")
        if accuracy is not None and macro_f1 is not None and accuracy - macro_f1 >= 0.15:
            warnings.append(
                f"{record.id}: accuracy is much higher than macro F1; check class imbalance."
            )
        for key, value in record.metrics.items():
            if "recall" in key.lower() and value < 0.6:
                warnings.append(f"{record.id}: {key} is still low ({value:g}).")
    return warnings


def _recommended_step(record: ExperimentRecord | None, ideas: list[str]) -> str:
    if record is None:
        return "Log a completed baseline experiment first."
    if any("class weights" in idea for idea in ideas):
        model = record.model or "the current model"
        return f"Try class-weighted loss for {model}."
    if any("early stopping" in idea for idea in ideas):
        return "Run the same model with early stopping and a lower learning rate."
    if any("baseline" in idea for idea in ideas):
        return "Validate the baseline and data pipeline before adding model complexity."
    return ideas[0] if ideas else "Run one controlled follow-up experiment."


def _suggested_config(record: ExperimentRecord | None) -> list[str]:
    model = record.model if record and record.model else "current best model"
    metric = next(iter(record.metrics), "macro_f1") if record else "macro_f1"
    return [
        f"model: {model}",
        "loss: weighted cross entropy if recall is low",
        "lr: 2e-5",
        "batch_size: 16",
        "epochs: 3",
        "early_stopping: true",
        f"metric: {metric}",
    ]


def _do_not_try_yet(pattern: str) -> list[str]:
    if "macro F1" in pattern or "Minority recall" in pattern:
        return [
            "Bigger model",
            "More epochs",
            "Complex ensemble",
            "Accuracy-only optimization",
        ]
    if "overfit" in pattern.lower() or "validation" in pattern.lower():
        return ["More epochs", "Larger model", "Uncontrolled hyperparameter sweep"]
    return ["Multiple simultaneous changes", "Complex ensemble before error analysis"]
