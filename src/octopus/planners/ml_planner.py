from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.paths import EXPERIMENT_MD, ML_DESIGN_MD
from octopus.core.schemas import ProjectState
from octopus.planners.ml_rules import MlPlanRules, rules_for_task
from octopus.planners.rendering import render_template


def render_ml_plan(state: ProjectState, *, backup: bool = True) -> MlPlanRules:
    rules = rules_for_task(state.task_type if state.task_type != "rag" else "rag")
    extra = {
        "baseline_models": rules.baseline_models,
        "metrics": rules.metrics,
        "risks": rules.risks,
        "first_experiment_note": rules.first_experiment_note,
        "main_metric": state.main_metric or rules.metrics[0],
    }
    backup_if_exists(ML_DESIGN_MD) if backup else None
    backup_if_exists(EXPERIMENT_MD) if backup else None
    atomic_write_text(ML_DESIGN_MD, render_template("ml_design.md.j2", state, **extra))
    atomic_write_text(EXPERIMENT_MD, render_template("experiment_plan.md.j2", state, **extra))
    return rules
