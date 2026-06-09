from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from octopus.core.schemas import BaselineProfile, ContextBuildResult, ExperimentRecord, TaskItem


class EmptyInput(BaseModel):
    pass


class StatusInput(BaseModel):
    include_files: bool = Field(default=True, description="Include generated file existence map.")
    include_context: bool = Field(default=True, description="Include current context metadata.")
    include_tasks: bool = Field(default=True, description="Include next task metadata.")


class FileStatus(BaseModel):
    path: str
    exists: bool


class ContextStatus(BaseModel):
    path: str
    exists: bool
    estimated_tokens: int | None = None
    modified_at: float | None = None


class StatusOutput(BaseModel):
    initialized: bool
    state_collected: bool
    project_complete: bool
    next_suggested_command: str
    project: dict[str, Any] = Field(default_factory=dict)
    files: list[FileStatus] = Field(default_factory=list)
    context: ContextStatus | None = None
    next_task: TaskItem | None = None


class TaskNextInput(BaseModel):
    include_done: bool = Field(default=False, description="Reserved for future task listing.")


class TaskNextOutput(BaseModel):
    task: TaskItem | None = None
    start_command: str | None = None
    message: str


class BuildContextInput(BaseModel):
    task: str | None = Field(default=None, description="Current task description.")
    profile: Literal["planning", "training", "debugging", "review"] = "training"
    budget: int = Field(default=6000, gt=0, description="Soft token budget.")
    full: bool = Field(default=False, description="Include all planning sections.")
    direction: str | None = Field(default=None, description="Selected direction ID, e.g. D1.")
    target: Literal["codex", "claude"] = "codex"
    write: bool = Field(default=True, description="Write current_context.md.")
    include_content: bool = Field(default=False, description="Return context text in the result.")


class BuildContextOutput(BaseModel):
    result: ContextBuildResult
    content: str | None = None


class IngestRunInput(BaseModel):
    run_dir: Path | None = Field(default=None, description="Training run directory.")
    metrics_path: Path | None = Field(default=None, description="metrics.json path.")
    report_path: Path | None = Field(default=None, description="classification_report.json path.")
    config_path: Path | None = Field(default=None, description="config.yaml/config.yml path.")
    name: str | None = None
    kind: str | None = Field(
        default=None,
        description="baseline, candidate, main, ablation, debug.",
    )
    model: str | None = None
    dataset: str | None = None
    notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tracker: Literal["auto", "mlflow", "wandb", "tensorboard", "none"] = "auto"


class IngestRunOutput(BaseModel):
    record: ExperimentRecord
    baseline_tasks_marked_done: bool = False
    next_command: str


class ProfileBaselineInput(BaseModel):
    experiment_id: str | None = Field(default=None, description="Baseline experiment ID.")
    top_k: int = Field(default=5, ge=1, le=20)
    write_report: bool = Field(default=True, description="Write baseline_profile.md.")


class ProfileBaselineOutput(BaseModel):
    profile: BaselineProfile
    output_path: str | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
