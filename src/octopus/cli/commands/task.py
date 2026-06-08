from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from octopus.core.files import atomic_write_text
from octopus.core.guards import require_complete_state
from octopus.core.paths import TASKS_MD
from octopus.core.workflow import has_completed_baseline, requires_baseline_gate
from octopus.storage.session_store import record_if_active
from octopus.storage.state_store import load_state
from octopus.storage.task_store import (
    blocked_dependencies,
    ensure_tasks,
    get_task,
    next_unblocked_task,
    render_tasks_markdown,
    save_tasks,
    set_task_status,
)

app = typer.Typer(help="Manage Octopus task state.")
console = Console()


def _load_managed_tasks():
    require_complete_state()
    state = load_state()
    return state, ensure_tasks(state)


def _write_task_view() -> None:
    state = load_state()
    tasks = ensure_tasks(state)
    atomic_write_text(TASKS_MD, render_tasks_markdown(state, tasks))


def _print_task(task_id: str, title: str, status: str) -> None:
    console.print(f"{task_id}: {title}")
    console.print(f"  Status: {status}")


@app.command("list")
def list_tasks(
    all_tasks: Annotated[
        bool,
        typer.Option("--all", help="Show done tasks as well as active tasks."),
    ] = False,
) -> None:
    _, tasks = _load_managed_tasks()
    table = Table(title="Octopus Tasks")
    table.add_column("ID", style="bold")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Depends on")
    for task in tasks:
        if not all_tasks and task.status == "done":
            continue
        table.add_row(task.id, task.status, task.title, ", ".join(task.depends_on) or "-")
    console.print(table)


@app.command("next")
def next_task() -> None:
    _, tasks = _load_managed_tasks()
    task = next_unblocked_task(tasks)
    if task is None:
        console.print("[green]No unblocked todo task found.[/green]")
        return
    _print_task(task.id, task.title, task.status)
    console.print(f"  Start with: octopus task start {task.id}")


@app.command("start")
def start_task(
    task_id: Annotated[str, typer.Argument(help="Task ID, for example T010.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Start even if dependencies are not done."),
    ] = False,
) -> None:
    state, tasks = _load_managed_tasks()
    task = get_task(tasks, task_id)
    if task is None:
        console.print(f"[red]Unknown task: {task_id}[/red]")
        raise typer.Exit(1)
    blocked = blocked_dependencies(task, tasks)
    if blocked and not force:
        console.print(f"[red]Task {task.id} is blocked.[/red]")
        console.print(f"Missing dependencies: {', '.join(blocked)}")
        if requires_baseline_gate(state) and "T012" in blocked:
            console.print("Log a completed baseline first:")
            console.print(
                "  octopus exp log --kind baseline --name baseline --metric "
                f"{state.main_metric or 'metric'}=<value>"
            )
        raise typer.Exit(1)
    task.status = "in_progress"
    save_tasks(tasks)
    _write_task_view()
    record_if_active(
        "task", f"Started {task.id}: {task.title}", current_task=f"{task.id} {task.title}"
    )
    console.print(f"[green]Task started:[/green] {task.id} {task.title}")


@app.command("done")
def complete_task(
    task_id: Annotated[str, typer.Argument(help="Task ID, for example T010.")],
) -> None:
    state, tasks = _load_managed_tasks()
    task = get_task(tasks, task_id)
    if task is None:
        console.print(f"[red]Unknown task: {task_id}[/red]")
        raise typer.Exit(1)
    if requires_baseline_gate(state) and task.id == "T012" and not has_completed_baseline():
        console.print(
            "[red]Cannot complete T012 before a real baseline experiment is logged.[/red]"
        )
        console.print("Run:")
        console.print(
            "  octopus exp log --kind baseline --name baseline --metric "
            f"{state.main_metric or 'metric'}=<value>"
        )
        raise typer.Exit(1)
    set_task_status(tasks, task.id, "done")
    _write_task_view()
    console.print(f"[green]Task completed:[/green] {task.id} {task.title}")


@app.command("reopen")
def reopen_task(
    task_id: Annotated[str, typer.Argument(help="Task ID, for example T010.")],
) -> None:
    _, tasks = _load_managed_tasks()
    task = get_task(tasks, task_id)
    if task is None:
        console.print(f"[red]Unknown task: {task_id}[/red]")
        raise typer.Exit(1)
    set_task_status(tasks, task.id, "todo")
    _write_task_view()
    console.print(f"[yellow]Task reopened:[/yellow] {task.id} {task.title}")
