from typing import Annotated

import typer

from octopus.cli.commands.ask import ask_requirements
from octopus.cli.commands.context import build_current_context
from octopus.cli.commands.exp import app as exp_app
from octopus.cli.commands.init import init_project
from octopus.cli.commands.ml_plan import generate_ml_plan
from octopus.cli.commands.plan import generate_plan
from octopus.cli.commands.status import show_status
from octopus.cli.commands.sync import sync_runtime
from octopus.cli.commands.tasks import generate_tasks

app = typer.Typer(help="Octopus CLI project brain for ML/DL planning.")
app.add_typer(exp_app, name="exp")


@app.command("init")
def init_cmd(
    runtime: Annotated[
        str, typer.Option("--runtime", help="Comma-separated runtimes.")
    ] = "claude,codex",
    force: Annotated[bool, typer.Option("--force", help="Overwrite without prompting.")] = False,
) -> None:
    init_project(runtime=runtime, force=force)


@app.command("ask")
def ask_cmd(reset: Annotated[bool, typer.Option("--reset")] = False) -> None:
    ask_requirements(reset=reset)


@app.command("plan")
def plan_cmd(force: Annotated[bool, typer.Option("--force")] = False) -> None:
    generate_plan(force=force)


@app.command("ml-plan")
def ml_plan_cmd(force: Annotated[bool, typer.Option("--force")] = False) -> None:
    generate_ml_plan(force=force)


@app.command("tasks")
def tasks_cmd(force: Annotated[bool, typer.Option("--force")] = False) -> None:
    generate_tasks(force=force)


@app.command("context")
def context_cmd(
    inspect_arg: Annotated[
        str | None, typer.Argument(help="Use 'inspect' to print context.")
    ] = None,
    task: Annotated[str | None, typer.Option("--task", help="Current task description.")] = None,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            help="Context profile: planning, training, debugging, or review.",
        ),
    ] = "training",
    budget: Annotated[
        int,
        typer.Option("--budget", help="Soft token budget for selected context sections."),
    ] = 6000,
    full: Annotated[
        bool,
        typer.Option("--full", help="Include all planning sections."),
    ] = False,
) -> None:
    build_current_context(
        task=task,
        inspect_arg=inspect_arg,
        profile=profile,
        budget=budget,
        full=full,
    )


@app.command("sync")
def sync_cmd(
    runtime: Annotated[
        str | None,
        typer.Option("--runtime", help="Runtime to sync: claude or codex."),
    ] = None,
) -> None:
    sync_runtime(runtime=runtime)


@app.command("status")
def status_cmd() -> None:
    show_status()


if __name__ == "__main__":
    app()
