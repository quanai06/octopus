from rich.console import Console

from octopus.core.guards import require_complete_state
from octopus.planners.task_planner import render_tasks
from octopus.storage.state_store import load_state
from octopus.storage.task_store import ensure_tasks

console = Console()


def generate_tasks(force: bool = False) -> None:
    require_complete_state()
    state = load_state()
    if state.project_type in {"machine learning", "deep learning", "rag"} and not state.task_type:
        console.print("[red]Machine learning task_type is required.[/red]")
        console.print("Run: [bold]octopus ask[/bold]")
        raise SystemExit(1)
    render_tasks(state, backup=not force)
    total_tasks = len(ensure_tasks(state))
    console.print("[green]tasks.md generated.[/green]\n")
    console.print("  Milestones:  5")
    console.print(f"  Total tasks: {total_tasks}")
    console.print("  Task state:  .octopus/tasks.json")
    console.print("  Baseline enforced: Yes (T010/T011/T012 before T020)")
