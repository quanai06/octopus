from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ComputeConfig(BaseModel):
    has_gpu: bool = False
    environment: str | None = None
    budget_note: str | None = None
    deadline: str | None = None


class ProjectState(BaseModel):
    project_name: str = ""
    project_goal: str | None = None
    target_users: str | None = None
    project_type: Literal["software", "ml", "dl", "rag", "research"] = "software"
    task_type: str | None = None
    input_type: str | None = None
    output_type: str | None = None
    dataset_status: Literal["available", "partial", "not_ready"] | None = None
    dataset_size_note: str | None = None
    has_labels: bool | None = None
    has_class_imbalance: bool | None = None
    main_metric: str | None = None
    target_score: float | None = None
    baseline_required: bool = True
    runtime: list[str] = Field(default_factory=list)
    compute: ComputeConfig = Field(default_factory=ComputeConfig)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskItem(BaseModel):
    id: str
    title: str
    priority: Literal["high", "medium", "low"]
    status: Literal["todo", "in_progress", "done"] = "todo"
    depends_on: list[str] = Field(default_factory=list)
    milestone: str | None = None
    description: str | None = None


class ContextBuildResult(BaseModel):
    task: str
    output_path: str
    estimated_tokens: int
    token_status: str
    included_files: list[str]
    excluded_files: list[str]
    excluded_patterns: list[str]
