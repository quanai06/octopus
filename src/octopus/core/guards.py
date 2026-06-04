import sys
from pathlib import Path

from rich.console import Console

from octopus.core.paths import OCTOPUS_DIR, REQUIREMENTS_MD, STATE_FILE

console = Console()


def require_init() -> None:
    if not OCTOPUS_DIR.exists():
        console.print("[red]Octopus not initialized.[/red]")
        console.print("Run: [bold]octopus init[/bold]")
        sys.exit(1)


def require_state() -> None:
    require_init()
    if not STATE_FILE.exists():
        console.print("[red]Project state not found.[/red]")
        console.print("Run: [bold]octopus ask[/bold]")
        sys.exit(1)


def require_complete_state() -> None:
    require_state()
    from octopus.storage.state_store import load_state

    state = load_state()
    if not state.project_name or not state.project_type:
        console.print("[red]Project state is incomplete.[/red]")
        console.print("Run: [bold]octopus ask[/bold]")
        sys.exit(1)


def require_ml_project() -> None:
    from octopus.storage.state_store import load_state

    state = load_state()
    if state.project_type not in ("machine learning", "deep learning", "rag"):
        console.print(
            "[yellow]ml-plan is only for machine learning/deep learning/RAG projects.[/yellow]"
        )
        console.print(f"Current type: {state.project_type}")
        sys.exit(0)


def require_plan_files() -> None:
    require_state()
    plan_files = [REQUIREMENTS_MD, Path("ml_design.md"), Path("tasks.md")]
    if not any(path.exists() for path in plan_files):
        console.print("[red]No plan files found.[/red]")
        console.print("Run: [bold]octopus plan[/bold] or [bold]octopus ml-plan[/bold] first.")
        sys.exit(1)
