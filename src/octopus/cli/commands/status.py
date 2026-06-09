import json
from builtins import print as raw_print

from rich.console import Console
from rich.table import Table

from octopus.core.paths import (
    AGENTS_MD,
    CLAUDE_MD,
    CURRENT_CONTEXT,
    EXPERIMENT_MD,
    ML_DESIGN_MD,
    OCTOPUS_DIR,
    REQUIREMENTS_MD,
    STATE_FILE,
    TASKS_MD,
)
from octopus.storage.state_store import load_state
from octopus.storage.task_store import ensure_tasks, next_unblocked_task
from octopus.tools.jsonio import dumps, success
from octopus.tools.registry import call_tool

console = Console()


def show_status(*, json_output: bool = False) -> None:
    if json_output:
        raw_print(dumps(success("octopus_status", call_tool("octopus_status"))), end="")
        return

    console.print("[bold]Octopus - Project Status[/bold]\n")
    if not OCTOPUS_DIR.exists():
        console.print("Octopus is not initialized.")
        console.print("Next suggested command: octopus init")
        return
    if not STATE_FILE.exists():
        console.print("Initialized, but project state has not been collected.")
        console.print("Next suggested command: octopus ask")
        return

    state = load_state()
    if not state.project_name:
        console.print("Initialized, but project details are empty.")
        console.print("Next suggested command: octopus ask")
        return

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Project", state.project_name)
    table.add_row("Type", state.task_type or state.project_type)
    table.add_row("Input", f"{state.input_type or '-'} -> {state.output_type or '-'}")
    table.add_row("Metric", state.main_metric or "-")
    table.add_row("Baseline", state.baseline_model or "default for task type")
    gpu = "Yes" if state.compute.has_gpu else "No"
    if state.compute.environment:
        gpu = f"{gpu} ({state.compute.environment})"
    table.add_row("GPU", gpu)
    table.add_row("Runtime", ", ".join(state.runtime) or "none")
    console.print(table)

    files = [REQUIREMENTS_MD, ML_DESIGN_MD, EXPERIMENT_MD, TASKS_MD, CLAUDE_MD, AGENTS_MD]
    console.print("\n[bold]Files[/bold]")
    for path in files:
        console.print(f"  {'OK' if path.exists() else '--'} {path.as_posix()}")

    console.print("\n[bold]Context[/bold]")
    if CURRENT_CONTEXT.exists():
        text = CURRENT_CONTEXT.read_text(encoding="utf-8")
        token_line = next(
            (line for line in text.splitlines() if line.startswith("> Estimated tokens:")),
            "> Estimated tokens: unknown",
        )
        console.print(f"  Last built: {CURRENT_CONTEXT.stat().st_mtime:.0f}")
        console.print(f"  {token_line.removeprefix('> ')}")
    else:
        console.print("  Not built yet.")

    tasks = ensure_tasks(state)
    task = next_unblocked_task(tasks)
    console.print("\n[bold]Tasks[/bold]")
    if task:
        console.print(f"  Next: {task.id} {task.title}")
        console.print(f"\nNext suggested command:\n  octopus task start {task.id}")
    else:
        console.print("  No unblocked todo task found.")


def state_file_payload() -> dict[str, object]:
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))
