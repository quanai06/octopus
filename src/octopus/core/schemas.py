from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ComputeConfig(BaseModel):
    has_gpu: bool = False
    environment: str | None = None
    budget_note: str | None = None
    deadline: str | None = None


class ProjectState(BaseModel):
    project_name: str = ""
    project_goal: str | None = None
    target_users: str | None = None
    project_type: str = "software"
    task_type: str | None = None
    input_type: str | None = None
    output_type: str | None = None
    dataset_status: str | None = None
    dataset_size_note: str | None = None
    has_labels: bool | None = None
    has_class_imbalance: bool | None = None
    main_metric: str | None = None
    baseline_model: str | None = None
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
    profile: str
    output_path: str
    estimated_tokens: int
    token_status: str
    included_files: list[str]
    included_sections: list[str] = Field(default_factory=list)
    skipped_sections: list[str] = Field(default_factory=list)
    excluded_files: list[str]
    excluded_patterns: list[str]


class PerClassMetrics(BaseModel):
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    support: int | None = None


class ExperimentArtifacts(BaseModel):
    run_dir: str | None = None
    log_path: str | None = None
    metrics_path: str | None = None
    report_path: str | None = None
    config_path: str | None = None
    checkpoint_path: str | None = None
    trainer_state_path: str | None = None


class ExperimentRecord(BaseModel):
    id: str = ""
    experiment_id: str = ""
    name: str
    kind: Literal["baseline", "candidate", "main", "ablation", "debug", "unknown", "other"] = (
        "unknown"
    )
    model: str | None = None
    dataset: str | None = None
    config_path: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    per_class: dict[str, PerClassMetrics] = Field(default_factory=dict)
    duration_sec: float | None = None
    timestamp: str | None = None
    notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: Literal["planned", "running", "completed", "failed", "skipped", "unknown"] = (
        "completed"
    )
    artifacts: ExperimentArtifacts = Field(default_factory=ExperimentArtifacts)
    diagnosis_id: str | None = None
    chosen_direction_id: str | None = None
    next_ideas: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "notes" not in data and "observation" in data:
                data["notes"] = data.pop("observation")
            if "experiment_id" not in data and "id" in data:
                data["experiment_id"] = data["id"]
            if "id" not in data and "experiment_id" in data:
                data["id"] = data["experiment_id"]
            if data.get("kind") == "other":
                data["kind"] = "other"
        return data

    @model_validator(mode="after")
    def sync_experiment_ids(self) -> "ExperimentRecord":
        if not self.experiment_id and self.id:
            self.experiment_id = self.id
        if not self.id and self.experiment_id:
            self.id = self.experiment_id
        return self


class DiagnosisSignal(BaseModel):
    name: str
    status: Literal["detected", "not_detected", "unknown"]
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence: list[str] = Field(default_factory=list)


class ExperimentDiagnosis(BaseModel):
    experiment_id: str
    main_metric: str | None = None
    main_metric_value: float | None = None
    baseline_delta: float | None = None
    best_delta: float | None = None
    target_gap: float | None = None
    signals: list[DiagnosisSignal] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    summary: str
    recommended_focus: list[str] = Field(default_factory=list)


class NextDirection(BaseModel):
    direction_id: str
    title: str
    priority: int
    recommendation: Literal["recommended", "optional", "avoid", "blocked"] = "optional"
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    cost: Literal["low", "medium", "high"] = "medium"
    expected_impact: str | None = None
    files_to_read: list[str] = Field(default_factory=list)
    files_to_edit: list[str] = Field(default_factory=list)
    files_to_avoid: list[str] = Field(default_factory=list)
    commands_to_run: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    stop_condition: str | None = None


class SelectedDirection(BaseModel):
    selected_direction_id: str
    selected_at: str
    source_plan: str
    status: Literal["selected", "completed", "abandoned"] = "selected"


class TechniqueSuggestion(BaseModel):
    technique_id: str
    name: str
    category: str
    why: str
    expected_effect: str
    cost: Literal["low", "medium", "high"] = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    guardrails: list[str] = Field(default_factory=list)


class WeakClass(BaseModel):
    label: str
    recall: float | None = None
    support: int | None = None


class BaselineProfile(BaseModel):
    experiment_id: str
    name: str
    domain: str
    main_metric: str | None = None
    main_metric_value: float | None = None
    target_score: float | None = None
    target_gap: float | None = None
    headroom: Literal["at_or_above_target", "small", "moderate", "large", "no_target"] = "no_target"
    bias_variance: Literal[
        "high_bias_underfit", "high_variance_overfit", "balanced", "undetermined"
    ] = "undetermined"
    readiness: Literal["no_baseline", "stabilize_baseline_first", "ready_to_tune"] = "ready_to_tune"
    detected_symptoms: list[str] = Field(default_factory=list)
    weak_classes: list[WeakClass] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)
    standing: str = ""
    summary: str = ""
    recommended_techniques: list[TechniqueSuggestion] = Field(default_factory=list)
    do_not_try_yet: list[str] = Field(default_factory=list)
