from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from octopus.tools.contracts import (
    BuildContextInput,
    BuildContextOutput,
    IngestRunInput,
    IngestRunOutput,
    ProfileBaselineInput,
    ProfileBaselineOutput,
    StatusInput,
    StatusOutput,
    TaskNextInput,
    TaskNextOutput,
    ToolSpec,
)
from octopus.tools.runtime import (
    build_context_tool,
    ingest_run_tool,
    profile_baseline_tool,
    status_tool,
    task_next_tool,
)


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[Any], BaseModel]

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
        )


TOOLS: dict[str, RegisteredTool] = {
    "octopus_status": RegisteredTool(
        name="octopus_status",
        description=(
            "Return initialized state, project snapshot, generated files, context, and next task."
        ),
        input_model=StatusInput,
        output_model=StatusOutput,
        handler=status_tool,
    ),
    "octopus_task_next": RegisteredTool(
        name="octopus_task_next",
        description="Return the next unblocked Octopus task and the command to start it.",
        input_model=TaskNextInput,
        output_model=TaskNextOutput,
        handler=task_next_tool,
    ),
    "octopus_build_context": RegisteredTool(
        name="octopus_build_context",
        description="Build a token-bounded working context for a task or selected direction.",
        input_model=BuildContextInput,
        output_model=BuildContextOutput,
        handler=build_context_tool,
    ),
    "octopus_ingest_run": RegisteredTool(
        name="octopus_ingest_run",
        description="Ingest metrics/artifacts from a run directory into Octopus experiment memory.",
        input_model=IngestRunInput,
        output_model=IngestRunOutput,
        handler=ingest_run_tool,
    ),
    "octopus_profile_baseline": RegisteredTool(
        name="octopus_profile_baseline",
        description="Profile the completed baseline and produce ranked next techniques.",
        input_model=ProfileBaselineInput,
        output_model=ProfileBaselineOutput,
        handler=profile_baseline_tool,
    ),
}


def list_tool_specs() -> list[ToolSpec]:
    return [tool.spec() for tool in TOOLS.values()]


def get_tool(name: str) -> RegisteredTool:
    try:
        return TOOLS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown Octopus tool: {name}") from exc


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> BaseModel:
    tool = get_tool(name)
    try:
        parsed = tool.input_model.model_validate(arguments or {})
    except ValidationError:
        raise
    result = tool.handler(parsed)
    return tool.output_model.model_validate(result)
