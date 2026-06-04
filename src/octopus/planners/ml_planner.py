from typing import Any

from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.paths import COMPUTE_BUDGET_MD, DATA_STRATEGY_MD, EXPERIMENT_MD, ML_DESIGN_MD
from octopus.core.schemas import ProjectState
from octopus.planners.ml_rules import MlPlanRules, rules_for_task
from octopus.planners.rendering import render_template


def _state_text(state: ProjectState) -> str:
    values = [
        state.project_name,
        state.project_goal,
        state.target_users,
        state.task_type,
        state.input_type,
        state.output_type,
        state.dataset_size_note,
    ]
    return " ".join(value for value in values if value).lower()


def _infer_language(state: ProjectState) -> str | None:
    text = _state_text(state)
    if any(marker in text for marker in ("vietnamese", "tiếng việt", "tieng viet", "phobert")):
        return "Vietnamese"
    if any(marker in text for marker in ("english", "bert-base-uncased", "roberta")):
        return "English"
    return None


def _model_candidates(state: ProjectState) -> list[str]:
    text = _state_text(state)
    if state.task_type == "text_classification":
        candidates = ["distilbert-base-multilingual-cased"]
        if any(marker in text for marker in ("vietnamese", "tiếng việt", "tieng viet", "phobert")):
            candidates.insert(0, "vinai/phobert-base")
        return candidates
    if state.task_type == "image_classification":
        return ["resnet50", "mobilenet_v3_small"]
    if state.task_type == "regression":
        return ["LightGBM", "XGBoost"]
    if state.task_type in {"retrieval", "rag"}:
        return [
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "cross-encoder reranker after retrieval baseline",
        ]
    return ["Strong baseline selected after data inspection"]


def _compute_budget_notes(state: ProjectState) -> list[str]:
    if state.compute.has_gpu:
        environment = state.compute.environment or "GPU environment"
        return [
            f"Use {environment} for transformer or neural model experiments.",
            "Start with one controlled run before sweeping hyperparameters.",
            "Track train time, peak memory, and inference latency for each run.",
        ]
    return [
        "Prioritize classical baselines and small models because no GPU is available.",
        "Defer transformer fine-tuning until GPU access is available.",
        "Use a sampled smoke test before full training.",
    ]


def _first_experiments(
    rules: MlPlanRules, candidates: list[str], baseline_models: list[str]
) -> list[str]:
    if rules.first_experiments:
        items = list(rules.first_experiments)
        selected_baseline = baseline_models[0]
        if not any(selected_baseline in item for item in items):
            items.insert(1 if items else 0, f"Train {selected_baseline} baseline.")
        return items
    return [
        rules.first_experiment_note,
        f"Train candidate model: {candidates[0]}",
        "Compare against baseline using the primary metric.",
    ]


def selected_baseline_models(state: ProjectState, rules: MlPlanRules) -> list[str]:
    if not state.baseline_model:
        return list(rules.baseline_models)
    remaining = [model for model in rules.baseline_models if model != state.baseline_model]
    return [state.baseline_model, *remaining]


def _planner_context(state: ProjectState, rules: MlPlanRules) -> dict[str, Any]:
    candidates = _model_candidates(state)
    baseline_models = selected_baseline_models(state, rules)
    metrics = rules.metrics
    secondary_metrics = metrics[1:] if len(metrics) > 1 else []
    first_experiment_note = f"Train a {baseline_models[0]} baseline."
    return {
        "problem_type": rules.problem_type,
        "language": _infer_language(state),
        "baseline_models": baseline_models,
        "metrics": metrics,
        "secondary_metrics": secondary_metrics,
        "risks": rules.risks,
        "first_experiment_note": first_experiment_note,
        "first_experiments": _first_experiments(rules, candidates, baseline_models),
        "main_metric": state.main_metric or metrics[0],
        "model_candidates": candidates,
        "data_checks": list(rules.data_checks),
        "training_checklist": list(rules.training_checklist),
        "compute_budget_notes": _compute_budget_notes(state),
    }


def render_ml_plan(state: ProjectState, *, backup: bool = True) -> MlPlanRules:
    rules = rules_for_task(state.task_type if state.task_type != "rag" else "rag")
    extra = _planner_context(state, rules)
    backup_if_exists(ML_DESIGN_MD) if backup else None
    backup_if_exists(EXPERIMENT_MD) if backup else None
    backup_if_exists(DATA_STRATEGY_MD) if backup else None
    backup_if_exists(COMPUTE_BUDGET_MD) if backup else None
    atomic_write_text(ML_DESIGN_MD, render_template("ml_design.md.j2", state, **extra))
    atomic_write_text(EXPERIMENT_MD, render_template("experiment_plan.md.j2", state, **extra))
    atomic_write_text(DATA_STRATEGY_MD, render_template("data_strategy.md.j2", state, **extra))
    atomic_write_text(COMPUTE_BUDGET_MD, render_template("compute_budget.md.j2", state, **extra))
    return rules
