from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from octopus.core.paths import (
    COMPUTE_BUDGET_MD,
    DATA_STRATEGY_MD,
    EXPERIMENT_MD,
    ML_DESIGN_MD,
    REQUIREMENTS_MD,
    TASKS_MD,
)

ContextProfile = Literal["planning", "training", "debugging", "review", "minimal-baseline"]

DEFAULT_PROFILE: ContextProfile = "training"
DEFAULT_TOKEN_BUDGET = 6_000


@dataclass(frozen=True)
class SectionRule:
    path: Path
    title_keywords: tuple[str, ...]
    priority: int


PROFILE_RULES: dict[ContextProfile, list[SectionRule]] = {
    "planning": [
        SectionRule(REQUIREMENTS_MD, ("project goal", "problem type", "evaluation"), 10),
        SectionRule(ML_DESIGN_MD, ("problem framing", "evaluation metrics", "known risks"), 20),
        SectionRule(DATA_STRATEGY_MD, ("dataset readiness", "split", "quality"), 30),
        SectionRule(TASKS_MD, ("milestone", "baseline", "data pipeline"), 40),
        SectionRule(COMPUTE_BUDGET_MD, ("compute", "budget", "limits"), 50),
    ],
    "training": [
        SectionRule(REQUIREMENTS_MD, ("project goal", "dataset", "evaluation", "compute"), 10),
        SectionRule(ML_DESIGN_MD, ("problem framing", "baseline", "candidate", "training"), 20),
        SectionRule(DATA_STRATEGY_MD, ("dataset readiness", "split", "quality", "leakage"), 30),
        SectionRule(EXPERIMENT_MD, ("goal", "baseline", "experiment", "stop condition"), 40),
        SectionRule(COMPUTE_BUDGET_MD, ("recommended", "resource", "runtime"), 50),
        SectionRule(TASKS_MD, ("data pipeline", "baseline", "main model"), 60),
    ],
    "minimal-baseline": [
        SectionRule(REQUIREMENTS_MD, ("dataset", "evaluation", "project goal"), 10),
        SectionRule(ML_DESIGN_MD, ("baseline contract", "baseline models"), 20),
        SectionRule(DATA_STRATEGY_MD, ("dataset readiness", "split", "leakage"), 30),
        SectionRule(EXPERIMENT_MD, ("baseline",), 40),
    ],
    "debugging": [
        SectionRule(REQUIREMENTS_MD, ("evaluation", "dataset", "constraints", "risks"), 10),
        SectionRule(ML_DESIGN_MD, ("known risks", "evaluation metrics", "training strategy"), 20),
        SectionRule(DATA_STRATEGY_MD, ("quality", "leakage", "imbalance", "validation"), 30),
        SectionRule(EXPERIMENT_MD, ("metrics", "decision", "stop condition", "experiment"), 40),
        SectionRule(TASKS_MD, ("review", "baseline", "main model"), 50),
    ],
    "review": [
        SectionRule(
            REQUIREMENTS_MD,
            ("project goal", "functional", "non-functional", "success"),
            10,
        ),
        SectionRule(ML_DESIGN_MD, ("problem framing", "evaluation", "known risks", "compute"), 20),
        SectionRule(DATA_STRATEGY_MD, ("dataset readiness", "validation", "leakage"), 30),
        SectionRule(EXPERIMENT_MD, ("goal", "experiment queue", "stop condition", "decision"), 40),
        SectionRule(COMPUTE_BUDGET_MD, ("limits", "risk", "recommended"), 50),
        SectionRule(TASKS_MD, ("milestone",), 60),
    ],
}


def normalize_profile(value: str | None) -> ContextProfile:
    if value is None:
        return DEFAULT_PROFILE
    profile = value.strip().lower()
    if profile not in PROFILE_RULES:
        choices = ", ".join(PROFILE_RULES)
        raise ValueError(f"Unknown profile '{value}'. Use one of: {choices}.")
    return profile  # type: ignore[return-value]
