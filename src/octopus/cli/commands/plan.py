from rich.console import Console

from octopus.core.guards import require_complete_state
from octopus.planners.requirement_planner import render_requirements
from octopus.storage.state_store import load_state

console = Console()


def generate_plan(force: bool = False) -> None:
    require_complete_state()
    render_requirements(load_state(), backup=not force)
    console.print("[green]requirements.md generated.[/green]\n")
    console.print("Run next:")
    console.print("  octopus ml-plan")
    console.print("  octopus tasks")
