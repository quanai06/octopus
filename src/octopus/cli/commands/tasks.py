from rich.console import Console

from octopus.core.guards import require_complete_state
from octopus.planners.task_planner import render_tasks
from octopus.storage.state_store import load_state

console = Console()


def generate_tasks(force: bool = False) -> None:
    require_complete_state()
    state = load_state()
    if state.project_type in {"ml", "dl", "rag"} and not state.task_type:
        console.print("[red]ML task_type is required.[/red]")
        console.print("Run: [bold]octopus ask[/bold]")
        raise SystemExit(1)
    content = render_tasks(state, backup=not force)
    total_tasks = content.count("- [ ] T")
    console.print("[green]tasks.md generated.[/green]\n")
    console.print("  Milestones:  5")
    console.print(f"  Total tasks: {total_tasks}")
    console.print("  Baseline enforced: Yes (T010 before T020)")
