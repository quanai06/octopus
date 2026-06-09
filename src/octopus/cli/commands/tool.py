from __future__ import annotations

import json
from builtins import print as raw_print
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from octopus.tools.jsonio import dumps, failure, success, to_jsonable
from octopus.tools.registry import call_tool, list_tool_specs

app = typer.Typer(help="Inspect and call structured Octopus tools.")
console = Console()


@app.command("list")
def list_tools(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    specs = list_tool_specs()
    if json_output:
        raw_print(dumps({"ok": True, "tools": specs}), end="")
        return
    table = Table(title="Octopus Tools")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    for spec in specs:
        table.add_row(spec.name, spec.description)
    console.print(table)


@app.command("call")
def call_structured_tool(
    name: Annotated[str, typer.Argument(help="Tool name, e.g. octopus_status.")],
    input_file: Annotated[
        Path | None,
        typer.Option("--input", help="JSON file containing tool arguments."),
    ] = None,
    input_json: Annotated[
        str | None,
        typer.Option("--input-json", help="Inline JSON object containing tool arguments."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable JSON."),
    ] = True,
) -> None:
    del json_output
    try:
        args = _read_args(input_file, input_json)
        result = call_tool(name, args)
    except (KeyError, ValueError, ValidationError, FileNotFoundError) as exc:
        raw_print(dumps(failure(name, exc)), end="")
        raise typer.Exit(1) from exc
    raw_print(dumps(success(name, result)), end="")


def _read_args(input_file: Path | None, input_json: str | None) -> dict:
    if input_file and input_json:
        raise ValueError("Use either --input or --input-json, not both.")
    if input_file:
        data = json.loads(input_file.read_text(encoding="utf-8"))
    elif input_json:
        data = json.loads(input_json)
    else:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Tool input must be a JSON object.")
    return to_jsonable(data)
