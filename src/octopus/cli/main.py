from pathlib import Path
from typing import Annotated

import typer

from octopus.cli.commands.ask import ask_from_file, ask_requirements
from octopus.cli.commands.context import build_current_context
from octopus.cli.commands.exp import app as exp_app
from octopus.cli.commands.init import init_project
from octopus.cli.commands.install import install_runtimes, uninstall_runtimes
from octopus.cli.commands.ml_plan import generate_ml_plan
from octopus.cli.commands.plan import generate_plan
from octopus.cli.commands.session import app as session_app
from octopus.cli.commands.session import resume as resume_session
from octopus.cli.commands.status import show_status
from octopus.cli.commands.sync import sync_runtime
from octopus.cli.commands.task import app as task_app
from octopus.cli.commands.tasks import generate_tasks
from octopus.cli.commands.tool import app as tool_app
from octopus.mcp_server import serve_stdio

app = typer.Typer(help="Octopus CLI project brain for machine learning/deep learning planning.")
app.add_typer(exp_app, name="exp")
app.add_typer(task_app, name="task")
app.add_typer(session_app, name="session")
app.add_typer(tool_app, name="tool")


@app.command("init")
def init_cmd(
    runtime: Annotated[
        str, typer.Option("--runtime", help="Comma-separated runtimes.")
    ] = "claude,codex",
    force: Annotated[bool, typer.Option("--force", help="Overwrite without prompting.")] = False,
) -> None:
    init_project(runtime=runtime, force=force)


@app.command("ask")
def ask_cmd(
    reset: Annotated[bool, typer.Option("--reset")] = False,
    from_file: Annotated[
        Path | None,
        typer.Option("--from", help="Non-interactive intake from a YAML/JSON answers file."),
    ] = None,
) -> None:
    if from_file is not None:
        ask_from_file(from_file)
    else:
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
    direction: Annotated[
        str | None,
        typer.Option("--direction", help="Build context for a selected experiment direction."),
    ] = None,
    target: Annotated[
        str,
        typer.Option("--target", help="Agent target for direction context: codex or claude."),
    ] = "codex",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print stable machine-readable JSON."),
    ] = False,
) -> None:
    build_current_context(
        task=task,
        inspect_arg=inspect_arg,
        profile=profile,
        budget=budget,
        full=full,
        direction=direction,
        target=target,
        json_output=json_output,
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
def status_cmd(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print stable machine-readable JSON."),
    ] = False,
) -> None:
    show_status(json_output=json_output)


@app.command("resume")
def resume_cmd() -> None:
    resume_session()


@app.command("install")
def install_cmd(
    runtime: Annotated[
        str, typer.Option("--runtime", help="Comma-separated runtimes: claude, codex.")
    ] = "claude,codex",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Base dir containing .claude/.codex (default: your home)."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite managed files.")] = False,
) -> None:
    install_runtimes(runtime=runtime, home=home, force=force)


@app.command("mcp")
def mcp_cmd() -> None:
    """Run the Octopus MCP server over stdio."""
    serve_stdio()


@app.command("uninstall")
def uninstall_cmd(
    runtime: Annotated[
        str, typer.Option("--runtime", help="Comma-separated runtimes: claude, codex.")
    ] = "claude,codex",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Base dir containing .claude/.codex (default: your home)."),
    ] = None,
) -> None:
    uninstall_runtimes(runtime=runtime, home=home)


if __name__ == "__main__":
    app()
