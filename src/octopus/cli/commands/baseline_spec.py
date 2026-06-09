from rich.console import Console

from octopus.core.guards import require_state
from octopus.planners.baseline_spec import render_baseline_spec
from octopus.storage.state_store import load_state

console = Console()


def generate_baseline_spec(force: bool = False) -> None:
    require_state()
    path = render_baseline_spec(load_state(), backup=not force)
    console.print(f"[green]{path.as_posix()} generated.[/green]\n")
    console.print("Use it as the small, fast-path baseline contract for Codex or scripts.")
