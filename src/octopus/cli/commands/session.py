from typing import Annotated

import typer
from rich.console import Console

from octopus.core.guards import require_init
from octopus.core.paths import (
    BASELINE_PROFILE_MD,
    CURRENT_CONTEXT,
    NEXT_STEPS_MD,
    SELECTED_DIRECTION_YAML,
)
from octopus.storage.session_store import (
    end_session,
    load_session,
    log_event,
    start_session,
)

app = typer.Typer(help="Manage short-term in-session memory.")
console = Console()


@app.command("start")
def start(
    goal: Annotated[str | None, typer.Option("--goal", help="What this session is about.")] = None,
) -> None:
    require_init()
    state = start_session(goal=goal)
    console.print(f"[green]Session started:[/green] {state.session_id}")
    if goal:
        console.print(f"  Goal: {goal}")


@app.command("show")
def show() -> None:
    require_init()
    state = load_session()
    if state is None:
        console.print("No active session. Start one with: octopus session start")
        return
    console.print(f"[bold]Session {state.session_id}[/bold] ({state.status})")
    console.print(f"  Goal: {state.goal or 'not set'}")
    console.print(f"  Current task: {state.current_task or 'none'}")
    console.print(f"  Selected direction: {state.selected_direction or 'none'}")
    console.print(f"  Last run: {state.last_run or 'none'}")
    if state.events:
        console.print("  Recent events:")
        for event in state.events[-5:]:
            console.print(f"    [{event.kind}] {event.message}")


@app.command("log")
def log(
    message: Annotated[str, typer.Argument(help="What happened.")],
    kind: Annotated[
        str, typer.Option("--kind", help="note, task, direction, run, or decision.")
    ] = "note",
) -> None:
    require_init()
    if kind not in {"note", "task", "direction", "run", "decision"}:
        console.print("[red]Invalid kind.[/red] Use: note, task, direction, run, decision.")
        raise typer.Exit(1)
    state = log_event(kind, message)
    if state is None:
        console.print("No active session. Start one with: octopus session start")
        raise typer.Exit(1)
    console.print("[green]Logged to session.[/green]")


@app.command("end")
def end() -> None:
    require_init()
    state = end_session()
    if state is None:
        console.print("No active session to end.")
        return
    console.print(f"[green]Session ended:[/green] {state.session_id}")


def resume() -> None:
    """Print a restore summary for a runtime that lost its context."""
    require_init()
    state = load_session()
    console.print("# Resume Octopus Work\n")
    if state is None or state.status != "active":
        console.print("No active session. Start one with: octopus session start")
    else:
        console.print(f"Active session: {state.session_id}")
        console.print(f"  Goal: {state.goal or 'not set'}")
        console.print(f"  Current task: {state.current_task or 'none'}")
        console.print(f"  Selected direction: {state.selected_direction or 'none'}")
        console.print(f"  Last run: {state.last_run or 'none'}")
        if state.events:
            console.print("  Recent events:")
            for event in state.events[-5:]:
                console.print(f"    [{event.kind}] {event.message}")
    console.print("\nRead these to restore context:")
    for path in (CURRENT_CONTEXT, SELECTED_DIRECTION_YAML, BASELINE_PROFILE_MD, NEXT_STEPS_MD):
        marker = "exists" if path.exists() else "missing"
        console.print(f"  {path.as_posix()} ({marker})")
    console.print("\nThen continue only the in-progress task/direction.")
