from datetime import UTC, datetime
from typing import cast

from rich.console import Console
from rich.panel import Panel

from octopus.core.config import save_config, touch_config
from octopus.core.guards import require_init
from octopus.core.schemas import ComputeConfig, ProjectState
from octopus.planners.ml_rules import rules_for_task
from octopus.storage.state_store import load_state, save_state, state_exists

console = Console()
CUSTOM_CHOICE = "custom..."
ProjectType = str
DatasetStatus = str


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


def _select_or_text(
    questionary,
    message: str,
    choices: list[str],
    default: str | None = None,
    *,
    custom_message: str | None = None,
    required: bool = True,
) -> str | None:
    options = list(choices)
    if default and default not in options:
        options.insert(0, default)
    if CUSTOM_CHOICE not in options:
        options.append(CUSTOM_CHOICE)
    selected = _select(questionary, message, options, default if default in options else None)
    if selected == CUSTOM_CHOICE:
        return _text(
            questionary,
            custom_message or f"Custom {message.rstrip('?').lower()}?",
            default=None,
            required=required,
        )
    return selected


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


def _checkbox_or_text(
    questionary,
    message: str,
    choices: list[str],
    default: list[str],
    *,
    custom_message: str,
) -> list[str]:
    options = list(choices)
    if CUSTOM_CHOICE not in options:
        options.append(CUSTOM_CHOICE)
    selected = _checkbox(questionary, message, options, default)
    if CUSTOM_CHOICE not in selected:
        return selected
    selected = [item for item in selected if item != CUSTOM_CHOICE]
    custom_value = _text(questionary, custom_message, required=True)
    if custom_value:
        selected.append(custom_value)
    return selected


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


def baseline_choices_for_task(task_type: str | None) -> list[str]:
    rules = rules_for_task(task_type if task_type != "rag" else "rag")
    return list(rules.baseline_models)


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

    console.print("[bold]Machine Learning / Deep Learning Problem[/bold]")
    project_type = cast(
        ProjectType,
        _select_or_text(
            questionary,
            "Project type?",
            ["software", "machine learning", "deep learning", "rag", "research"],
            existing.project_type,
            custom_message="Custom project type?",
        ),
    )
    is_ml_like = project_type in {"machine learning", "deep learning", "rag"}
    task_type = existing.task_type
    input_type = existing.input_type
    dataset_status = existing.dataset_status
    dataset_size_note = existing.dataset_size_note
    has_labels = existing.has_labels
    has_class_imbalance = existing.has_class_imbalance
    baseline_model = existing.baseline_model
    if is_ml_like:
        task_type = _select_or_text(
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
            ],
            task_type,
            custom_message="Custom task type?",
        )
        baseline_choices = baseline_choices_for_task(task_type)
        if baseline_model and baseline_model not in baseline_choices:
            baseline_choices.insert(0, baseline_model)
        baseline_model = _select_or_text(
            questionary,
            "Baseline model?",
            baseline_choices,
            baseline_model if baseline_model in baseline_choices else baseline_choices[0],
            custom_message="Custom baseline model?",
        )
        input_type = _select_or_text(
            questionary,
            "Input type?",
            ["text", "image", "tabular", "audio", "video", "multimodal", "documents"],
            input_type,
            custom_message="Custom input type?",
        )
        output_type = _text(questionary, "Output type?", output_type, required=True)
        dataset_status = cast(
            DatasetStatus,
            _select_or_text(
                questionary,
                "Dataset status?",
                ["available", "partial", "not_ready"],
                dataset_status,
                custom_message="Custom dataset status?",
            ),
        )
        dataset_size_note = _text(questionary, "Dataset size note?", dataset_size_note)
        has_labels = _confirm(questionary, "Do you already have labels?", has_labels)
        has_class_imbalance = _confirm(
            questionary, "Is there class imbalance?", has_class_imbalance
        )

    console.print("[bold]Evaluation[/bold]")
    main_metric = _select_or_text(
        questionary,
        "Main metric?",
        ["macro_f1", "accuracy", "MAE", "RMSE", "Recall@k", "MRR"],
        existing.main_metric,
        custom_message="Custom main metric?",
    )
    target_score = _float_or_none(
        _text(questionary, "Target score?", str(existing.target_score or ""))
    )
    budget_note = _text(questionary, "Latency / cost constraints?", existing.compute.budget_note)

    console.print("[bold]Compute & Runtime[/bold]")
    has_gpu = _confirm(questionary, "Do you have GPU?", existing.compute.has_gpu)
    environment = existing.compute.environment
    if has_gpu:
        environment = _select_or_text(
            questionary,
            "Environment?",
            ["local", "colab_t4", "colab_a100", "kaggle", "server"],
            environment,
            custom_message="Custom environment?",
        )
    deadline = _text(questionary, "Budget / deadline?", existing.compute.deadline)
    runtime = _checkbox_or_text(
        questionary,
        "Runtime?",
        ["claude", "codex", "none"],
        existing.runtime or ["claude", "codex"],
        custom_message="Custom runtime? Use a short name such as cursor or aider.",
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
        baseline_model=baseline_model if is_ml_like else None,
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
