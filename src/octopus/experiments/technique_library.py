"""Deterministic ML/DL/RAG technique knowledge base.

Maps diagnosed *symptoms* (the signal names produced by ``analyze.py``) to
concrete, domain-aware tuning techniques. This is the canonical source for
"what should I try next on top of the baseline" so the same knowledge can feed
the baseline profile, next-step planner, and runtime agent context.

Everything here is rule-based and offline. No model is consulted.
"""

from __future__ import annotations

from dataclasses import dataclass

# Symptom vocabulary (aligned with octopus.experiments.analyze signal names,
# plus a few profile-level symptoms derived from headroom/standing).
SYMPTOM_CLASS_IMBALANCE = "class_imbalance"
SYMPTOM_METRIC_GAP = "metric_gap"
SYMPTOM_OVERFITTING = "overfitting"
SYMPTOM_UNDERFITTING = "underfitting"
SYMPTOM_UNSTABLE = "unstable_training"
SYMPTOM_LOW_RETRIEVAL = "low_retrieval"
SYMPTOM_NEAR_TARGET = "near_target"
SYMPTOM_LARGE_GAP = "large_gap"
SYMPTOM_HEALTHY = "baseline_healthy"

# Domains. Task types collapse into one of these.
DOMAIN_CLASSIFICATION = "classification"
DOMAIN_REGRESSION = "regression"
DOMAIN_RAG = "rag"
DOMAIN_GENERIC = "generic"
ALL_DOMAINS = "*"

_TASK_TO_DOMAIN = {
    "text_classification": DOMAIN_CLASSIFICATION,
    "image_classification": DOMAIN_CLASSIFICATION,
    "classification": DOMAIN_CLASSIFICATION,
    "regression": DOMAIN_REGRESSION,
    "forecasting": DOMAIN_REGRESSION,
    "retrieval": DOMAIN_RAG,
    "retrieval_qa": DOMAIN_RAG,
    "rag": DOMAIN_RAG,
}

_PROJECT_TO_DOMAIN = {"rag": DOMAIN_RAG}


@dataclass(frozen=True)
class Technique:
    technique_id: str
    name: str
    category: str  # data | sampling | loss | optim | regularization | architecture
    #              | evaluation | retrieval | generation
    domains: tuple[str, ...]
    symptoms: tuple[str, ...]
    why: str
    expected_effect: str
    cost: str = "medium"  # low | medium | high
    risk: str = "medium"
    guardrails: tuple[str, ...] = ()


@dataclass(frozen=True)
class AntiPattern:
    name: str
    symptoms: tuple[str, ...]
    reason: str


# Ordering weights so cheap, safe, high-leverage techniques rank first.
_COST_RANK = {"low": 0, "medium": 1, "high": 2}
_RISK_RANK = {"low": 0, "medium": 1, "high": 2}


def domain_for(task_type: str | None, project_type: str | None = None) -> str:
    """Collapse a task/project type into a technique domain."""
    if project_type and project_type.lower() in _PROJECT_TO_DOMAIN:
        return _PROJECT_TO_DOMAIN[project_type.lower()]
    if task_type and task_type.lower() in _TASK_TO_DOMAIN:
        return _TASK_TO_DOMAIN[task_type.lower()]
    return DOMAIN_GENERIC


TECHNIQUES: list[Technique] = [
    # --- Class imbalance / minority recall (classification) ---
    Technique(
        technique_id="cls_class_weights",
        name="Class-weighted loss",
        category="loss",
        domains=(DOMAIN_CLASSIFICATION,),
        symptoms=(SYMPTOM_CLASS_IMBALANCE, SYMPTOM_METRIC_GAP),
        why="Re-weights the loss so minority classes are not drowned out by the majority.",
        expected_effect="Higher minority recall and macro F1 with no architecture change.",
        cost="low",
        risk="low",
        guardrails=(
            "Change only the class weights in the next run.",
            "Track macro F1 and per-class recall, not accuracy.",
        ),
    ),
    Technique(
        technique_id="cls_weighted_sampler",
        name="Weighted / balanced sampling",
        category="sampling",
        domains=(DOMAIN_CLASSIFICATION,),
        symptoms=(SYMPTOM_CLASS_IMBALANCE,),
        why="Balances class frequency per batch so gradients are not majority-dominated.",
        expected_effect="More stable minority-class learning.",
        cost="low",
        risk="low",
        guardrails=("Keep the validation/test split untouched.",),
    ),
    Technique(
        technique_id="cls_focal_loss",
        name="Focal loss",
        category="loss",
        domains=(DOMAIN_CLASSIFICATION,),
        symptoms=(SYMPTOM_CLASS_IMBALANCE, SYMPTOM_METRIC_GAP),
        why="Down-weights easy majority examples and focuses learning on hard minority ones.",
        expected_effect="Improves hard-class recall when class weights plateau.",
        cost="low",
        risk="medium",
        guardrails=("Tune gamma after class weights, not before.",),
    ),
    Technique(
        technique_id="cls_threshold_tuning",
        name="Per-class decision threshold tuning",
        category="evaluation",
        domains=(DOMAIN_CLASSIFICATION,),
        symptoms=(SYMPTOM_CLASS_IMBALANCE, SYMPTOM_METRIC_GAP, SYMPTOM_NEAR_TARGET),
        why="Default 0.5 thresholds are rarely optimal under imbalance.",
        expected_effect="Recovers macro F1 cheaply without retraining.",
        cost="low",
        risk="low",
        guardrails=("Fit thresholds on validation only, never on test.",),
    ),
    Technique(
        technique_id="cls_minority_augment",
        name="Minority-class augmentation / oversampling",
        category="data",
        domains=(DOMAIN_CLASSIFICATION,),
        symptoms=(SYMPTOM_CLASS_IMBALANCE,),
        why="Adds minority signal (EDA/back-translation for text, transforms for images, "
        "SMOTE for tabular).",
        expected_effect="More minority coverage when re-weighting is not enough.",
        cost="medium",
        risk="medium",
        guardrails=("Augment train only; never leak augmented copies into val/test.",),
    ),
    # --- Overfitting (high variance) ---
    Technique(
        technique_id="reg_early_stopping",
        name="Early stopping",
        category="regularization",
        domains=(DOMAIN_CLASSIFICATION, DOMAIN_REGRESSION, ALL_DOMAINS),
        symptoms=(SYMPTOM_OVERFITTING,),
        why="Stops training once validation quality stops improving.",
        expected_effect="Recovers the best checkpoint and avoids wasted epochs.",
        cost="low",
        risk="low",
        guardrails=("Monitor the main metric on validation, not train loss.",),
    ),
    Technique(
        technique_id="reg_weight_decay_dropout",
        name="Weight decay & dropout",
        category="regularization",
        domains=(DOMAIN_CLASSIFICATION, ALL_DOMAINS),
        symptoms=(SYMPTOM_OVERFITTING,),
        why="Penalizes large weights and co-adaptation to reduce memorization.",
        expected_effect="Smaller train/val gap.",
        cost="low",
        risk="low",
        guardrails=("Change one regularizer at a time.",),
    ),
    Technique(
        technique_id="reg_data_augment",
        name="Training-data augmentation",
        category="data",
        domains=(DOMAIN_CLASSIFICATION,),
        symptoms=(SYMPTOM_OVERFITTING,),
        why="Increases effective dataset size and invariance.",
        expected_effect="Better generalization without a bigger model.",
        cost="medium",
        risk="medium",
        guardrails=("Add augmentation only after a no-augmentation baseline exists.",),
    ),
    # --- Underfitting (high bias) ---
    Technique(
        technique_id="bias_sanity_overfit",
        name="One-batch overfit sanity check",
        category="evaluation",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_UNDERFITTING,),
        why="Confirms the model+pipeline can fit a tiny sample before scaling up.",
        expected_effect="Catches preprocessing/label bugs cheaply.",
        cost="low",
        risk="low",
        guardrails=("If a single batch cannot be overfit, fix the pipeline first.",),
    ),
    Technique(
        technique_id="bias_features_capacity",
        name="Stronger features / model capacity",
        category="architecture",
        domains=(DOMAIN_CLASSIFICATION, DOMAIN_REGRESSION),
        symptoms=(SYMPTOM_UNDERFITTING,),
        why="A too-simple model or weak features cannot reach the target.",
        expected_effect="Raises the achievable ceiling.",
        cost="medium",
        risk="medium",
        guardrails=("Only escalate capacity after the pipeline is verified.",),
    ),
    Technique(
        technique_id="bias_lr_schedule",
        name="Learning-rate schedule / longer training",
        category="optim",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_UNDERFITTING,),
        why="Under-trained models look like high bias.",
        expected_effect="Better convergence at low extra cost.",
        cost="low",
        risk="low",
    ),
    # --- Unstable training ---
    Technique(
        technique_id="opt_lower_lr_warmup",
        name="Lower LR + warmup",
        category="optim",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_UNSTABLE,),
        why="High learning rates cause loss spikes and divergence.",
        expected_effect="Smoother, repeatable loss curves.",
        cost="low",
        risk="low",
    ),
    Technique(
        technique_id="opt_grad_clip",
        name="Gradient clipping & NaN guard",
        category="optim",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_UNSTABLE,),
        why="Bounds exploding gradients and surfaces NaN/inf early.",
        expected_effect="Stops divergence from bad batches or mixed precision.",
        cost="low",
        risk="low",
        guardrails=("Inspect data for NaN/inf and bad samples too.",),
    ),
    # --- Regression-specific ---
    Technique(
        technique_id="reg_robust_loss",
        name="Robust loss / outlier handling",
        category="loss",
        domains=(DOMAIN_REGRESSION,),
        symptoms=(SYMPTOM_UNDERFITTING, SYMPTOM_LARGE_GAP, SYMPTOM_HEALTHY),
        why="Outliers dominate squared error; Huber/quantile loss is more stable.",
        expected_effect="Lower RMSE/MAE when residuals are heavy-tailed.",
        cost="low",
        risk="low",
        guardrails=("Inspect residuals by segment before changing the loss.",),
    ),
    Technique(
        technique_id="reg_target_transform",
        name="Target transform (log/Box-Cox)",
        category="data",
        domains=(DOMAIN_REGRESSION,),
        symptoms=(SYMPTOM_LARGE_GAP, SYMPTOM_HEALTHY),
        why="Skewed targets hurt linear and tree models.",
        expected_effect="Stabilizes variance and improves fit.",
        cost="low",
        risk="medium",
        guardrails=("Invert the transform before computing reported metrics.",),
    ),
    Technique(
        technique_id="reg_gbm",
        name="Gradient-boosted trees baseline",
        category="architecture",
        domains=(DOMAIN_REGRESSION,),
        symptoms=(SYMPTOM_UNDERFITTING, SYMPTOM_LARGE_GAP),
        why="Strong tabular ceiling above linear models.",
        expected_effect="Often a large jump over a linear baseline.",
        cost="medium",
        risk="low",
    ),
    # --- RAG / retrieval-specific ---
    Technique(
        technique_id="rag_eval_first",
        name="Retrieval evaluation set first",
        category="evaluation",
        domains=(DOMAIN_RAG,),
        symptoms=(SYMPTOM_LOW_RETRIEVAL, SYMPTOM_HEALTHY, SYMPTOM_LARGE_GAP),
        why="Generation quality cannot be improved before retrieval is measured.",
        expected_effect="Separates retrieval bottlenecks from generation bottlenecks.",
        cost="medium",
        risk="low",
        guardrails=(
            "Report Recall@k / source-hit on a fixed query set.",
            "Do not tune on private eval answers.",
        ),
    ),
    Technique(
        technique_id="rag_chunking",
        name="Chunk size & overlap tuning",
        category="retrieval",
        domains=(DOMAIN_RAG,),
        symptoms=(SYMPTOM_LOW_RETRIEVAL,),
        why="Bad chunk boundaries split answers across passages.",
        expected_effect="Higher Recall@k with no model change.",
        cost="low",
        risk="low",
    ),
    Technique(
        technique_id="rag_hybrid",
        name="Hybrid BM25 + dense retrieval",
        category="retrieval",
        domains=(DOMAIN_RAG,),
        symptoms=(SYMPTOM_LOW_RETRIEVAL,),
        why="Lexical and semantic retrieval cover different failure cases.",
        expected_effect="More robust recall across query types.",
        cost="medium",
        risk="low",
    ),
    Technique(
        technique_id="rag_reranker",
        name="Cross-encoder reranker",
        category="retrieval",
        domains=(DOMAIN_RAG,),
        symptoms=(SYMPTOM_LOW_RETRIEVAL, SYMPTOM_NEAR_TARGET),
        why="Reranks a larger candidate set for higher precision@k.",
        expected_effect="Better top-k ordering after recall is sufficient.",
        cost="medium",
        risk="medium",
        guardrails=("Increase candidate top-k first, then rerank.",),
    ),
    Technique(
        technique_id="rag_faithfulness",
        name="Citation & faithfulness checks",
        category="generation",
        domains=(DOMAIN_RAG,),
        symptoms=(SYMPTOM_HEALTHY, SYMPTOM_NEAR_TARGET),
        why="Grounded answers need source citations, not just high recall.",
        expected_effect="Reduces hallucination and unsupported answers.",
        cost="medium",
        risk="low",
        guardrails=("Every answer must cite a retrieved source chunk.",),
    ),
    # --- Healthy baseline / refinement (all domains) ---
    Technique(
        technique_id="gen_error_analysis",
        name="Slice-based error analysis",
        category="evaluation",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_HEALTHY, SYMPTOM_NEAR_TARGET, SYMPTOM_LARGE_GAP),
        why="Real mistakes point to the next controlled experiment.",
        expected_effect="Turns a vague gap into one measurable bottleneck.",
        cost="low",
        risk="low",
        guardrails=("Inspect the confusion matrix and worst slices first.",),
    ),
    Technique(
        technique_id="gen_seed_ensemble",
        name="Seed averaging / small ensemble",
        category="architecture",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_NEAR_TARGET,),
        why="Cheap variance reduction when close to the target.",
        expected_effect="A small, low-risk metric bump.",
        cost="medium",
        risk="low",
    ),
    Technique(
        technique_id="data_leakage_audit",
        name="Data-leakage & split audit",
        category="data",
        domains=(ALL_DOMAINS,),
        symptoms=(SYMPTOM_METRIC_GAP, SYMPTOM_OVERFITTING),
        why="Suspiciously high or uneven metrics often signal leakage or split bugs.",
        expected_effect="Prevents chasing inflated metrics.",
        cost="low",
        risk="low",
        guardrails=("Check for duplicate/near-duplicate samples across splits.",),
    ),
]


ANTI_PATTERNS: list[AntiPattern] = [
    AntiPattern(
        name="Switch to a bigger backbone",
        symptoms=(SYMPTOM_CLASS_IMBALANCE, SYMPTOM_METRIC_GAP),
        reason="A larger model rarely fixes per-class imbalance; fix the objective/sampling first.",
    ),
    AntiPattern(
        name="Train for more epochs",
        symptoms=(SYMPTOM_OVERFITTING,),
        reason="More epochs deepen overfitting; regularize or stop early instead.",
    ),
    AntiPattern(
        name="Optimize accuracy only",
        symptoms=(SYMPTOM_CLASS_IMBALANCE, SYMPTOM_METRIC_GAP),
        reason="Accuracy hides minority-class failure; select on macro F1.",
    ),
    AntiPattern(
        name="Increase model complexity",
        symptoms=(SYMPTOM_UNSTABLE,),
        reason="Stabilize optimization before adding capacity.",
    ),
    AntiPattern(
        name="Tune generation/prompts",
        symptoms=(SYMPTOM_LOW_RETRIEVAL,),
        reason="Fix retrieval recall before touching the generator.",
    ),
    AntiPattern(
        name="Run a broad hyperparameter sweep",
        symptoms=(SYMPTOM_UNDERFITTING,),
        reason="Verify the pipeline with a one-batch overfit check before sweeping.",
    ),
]


def _technique_rank(technique: Technique, symptoms: set[str]) -> tuple[int, int, int]:
    overlap = len(set(technique.symptoms) & symptoms)
    return (
        -overlap,
        _COST_RANK.get(technique.cost, 1),
        _RISK_RANK.get(technique.risk, 1),
    )


def techniques_for(domain: str, symptoms: list[str], limit: int | None = None) -> list[Technique]:
    """Return techniques matching the domain and at least one symptom, ranked.

    Cheaper and lower-risk techniques that address more of the detected symptoms
    rank first.
    """
    wanted = set(symptoms)
    matched = [
        technique
        for technique in TECHNIQUES
        if (domain in technique.domains or ALL_DOMAINS in technique.domains)
        and wanted.intersection(technique.symptoms)
    ]
    matched.sort(key=lambda technique: _technique_rank(technique, wanted))
    return matched[:limit] if limit else matched


def antipatterns_for(symptoms: list[str]) -> list[AntiPattern]:
    wanted = set(symptoms)
    return [anti for anti in ANTI_PATTERNS if wanted.intersection(anti.symptoms)]
