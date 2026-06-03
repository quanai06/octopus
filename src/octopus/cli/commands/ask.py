from datetime import UTC, datetime
from typing import Literal, cast

from rich.console import Console
from rich.panel import Panel

from octopus.core.config import save_config, touch_config
from octopus.core.guards import require_init
from octopus.core.schemas import ComputeConfig, ProjectState
from octopus.storage.state_store import load_state, save_state, state_exists

console = Console()
ProjectType = Literal["software", "ml", "dl", "rag", "research"]
DatasetStatus = Literal["available", "partial", "not_ready"]


def _text(
    questionary, message: str, default: str | None = None, required: bool = False
) -> str | None:
    while True:
        answer = questionary.text(message, default=default or "").ask()
        if answer is None:
            raise KeyboardInterrupt
        answer = answer.strip()
        if answer or not required:
            return answer or None
        console.print("[red]This field is required.[/red]")


def _select(questionary, message: str, choices: list[str], default: str | None = None) -> str:
    answer = questionary.select(message, choices=choices, default=default).ask()
    if answer is None:
        raise KeyboardInterrupt
    return str(answer)


def _checkbox(questionary, message: str, choices: list[str], default: list[str]) -> list[str]:
    selected = set(default)
    checkbox_choices = [
        questionary.Choice(title=choice, value=choice, checked=choice in selected)
        for choice in choices
    ]
    answer = questionary.checkbox(message, choices=checkbox_choices).ask()
    if answer is None:
        raise KeyboardInterrupt
    return [str(item) for item in answer if item != "none"]


def _confirm(questionary, message: str, default: bool | None = None) -> bool | None:
    answer = questionary.confirm(message, default=bool(default)).ask()
    if answer is None:
        raise KeyboardInterrupt
    return bool(answer)


def _float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        console.print("[yellow]Target score ignored because it is not a number.[/yellow]")
        return None


def ask_requirements(reset: bool = False) -> None:
    require_init()
    import questionary

    existing = load_state() if state_exists() and not reset else ProjectState()
    console.print(Panel("Octopus requirement intake", title="Project Planning"))

    console.print("[bold]Project Overview[/bold]")
    project_name = _text(questionary, "Project name?", existing.project_name, required=True)
    project_goal = _text(questionary, "Main project goal?", existing.project_goal, required=True)
    target_users = _text(questionary, "Target users?", existing.target_users)
    output_type = _text(questionary, "Desired output?", existing.output_type)

    console.print("[bold]ML / DL Problem[/bold]")
    project_type = cast(
        ProjectType,
        _select(
            questionary,
            "Project type?",
            ["software", "ml", "dl", "rag", "research"],
            existing.project_type,
        ),
    )
    is_ml_like = project_type in {"ml", "dl", "rag"}
    task_type = existing.task_type
    input_type = existing.input_type
    dataset_status = existing.dataset_status
    dataset_size_note = existing.dataset_size_note
    has_labels = existing.has_labels
    has_class_imbalance = existing.has_class_imbalance
    if is_ml_like:
        task_type = _select(
            questionary,
            "Task type?",
            [
                "text_classification",
                "image_classification",
                "regression",
                "retrieval",
                "recommendation",
                "forecasting",
                "clustering",
                "anomaly_detection",
                "rag",
                "other",
            ],
            task_type,
        )
        if task_type == "other":
            task_type = _text(questionary, "Custom task type?", existing.task_type, required=True)
        input_type = _select(
            questionary,
            "Input type?",
            ["text", "image", "tabular", "audio", "video", "multimodal", "documents"],
            input_type,
        )
        output_type = _text(questionary, "Output type?", output_type, required=True)
        dataset_status = cast(
            DatasetStatus,
            _select(
                questionary,
                "Dataset status?",
                ["available", "partial", "not_ready"],
                dataset_status,
            ),
        )
        dataset_size_note = _text(questionary, "Dataset size note?", dataset_size_note)
        has_labels = _confirm(questionary, "Do you already have labels?", has_labels)
        has_class_imbalance = _confirm(
            questionary, "Is there class imbalance?", has_class_imbalance
        )

    console.print("[bold]Evaluation[/bold]")
    main_metric = _select(
        questionary,
        "Main metric?",
        ["macro_f1", "accuracy", "MAE", "RMSE", "Recall@k", "MRR", "custom"],
        existing.main_metric,
    )
    if main_metric == "custom":
        custom_metric = _text(
            questionary, "Custom main metric?", existing.main_metric, required=True
        )
        main_metric = custom_metric or existing.main_metric or "custom"
    target_score = _float_or_none(
        _text(questionary, "Target score?", str(existing.target_score or ""))
    )
    budget_note = _text(questionary, "Latency / cost constraints?", existing.compute.budget_note)

    console.print("[bold]Compute & Runtime[/bold]")
    has_gpu = _confirm(questionary, "Do you have GPU?", existing.compute.has_gpu)
    environment = existing.compute.environment
    if has_gpu:
        environment = _select(
            questionary,
            "Environment?",
            ["local", "colab_t4", "colab_a100", "kaggle", "server"],
            environment,
        )
    deadline = _text(questionary, "Budget / deadline?", existing.compute.deadline)
    runtime = _checkbox(
        questionary,
        "Runtime?",
        ["claude", "codex", "none"],
        existing.runtime or ["claude", "codex"],
    )

    now = datetime.now(UTC)
    state = ProjectState(
        project_name=project_name or "",
        project_goal=project_goal,
        target_users=target_users,
        project_type=project_type,
        task_type=task_type,
        input_type=input_type,
        output_type=output_type,
        dataset_status=dataset_status,
        dataset_size_note=dataset_size_note,
        has_labels=has_labels,
        has_class_imbalance=has_class_imbalance,
        main_metric=main_metric,
        target_score=target_score,
        runtime=runtime,
        compute=ComputeConfig(
            has_gpu=bool(has_gpu),
            environment=environment if has_gpu else None,
            budget_note=budget_note,
            deadline=deadline,
        ),
        created_at=existing.created_at,
        last_updated=now,
    )
    save_state(state)
    try:
        touch_config()
    except FileNotFoundError:
        save_config(
            {
                "version": "0.1.0",
                "runtime": runtime,
                "created_at": now.isoformat(),
                "last_updated": now.isoformat(),
            }
        )

    console.print("\n[green]Project state saved.[/green]\n")
    console.print(f"  Project: {state.project_name}")
    console.print(f"  Type:    {state.task_type or state.project_type}")
    console.print(f"  Metric:  {state.main_metric or 'not set'}")
    console.print(f"  Runtime: {', '.join(state.runtime) or 'none'}")
    console.print("\nRun next:\n  octopus plan\n  octopus ml-plan")
