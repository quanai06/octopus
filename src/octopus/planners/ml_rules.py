from dataclasses import dataclass


@dataclass(frozen=True)
class MlPlanRules:
    baseline_models: list[str]
    metrics: list[str]
    risks: list[str]
    first_experiment_note: str
    generic: bool = False


RULE_MAP: dict[str, MlPlanRules] = {
    "text_classification": MlPlanRules(
        baseline_models=["TF-IDF + Logistic Regression", "TF-IDF + LinearSVC"],
        metrics=["macro_f1", "per-class recall", "confusion matrix"],
        risks=["class imbalance", "noisy text", "data leakage", "overfitting"],
        first_experiment_note="Train a TF-IDF + Logistic Regression baseline.",
    ),
    "image_classification": MlPlanRules(
        baseline_models=["Pretrained ResNet", "MobileNet"],
        metrics=["accuracy", "macro_f1 if imbalanced"],
        risks=["incorrect augmentation", "train/val leakage", "class imbalance"],
        first_experiment_note="Fine-tune a small pretrained CNN baseline.",
    ),
    "regression": MlPlanRules(
        baseline_models=["Linear Regression", "Random Forest", "LightGBM"],
        metrics=["MAE", "RMSE", "R2"],
        risks=["outliers", "data leakage", "target skew"],
        first_experiment_note="Train Linear Regression and compare with a tree baseline.",
    ),
    "retrieval": MlPlanRules(
        baseline_models=["BM25", "Dense embedding retrieval"],
        metrics=["Recall@k", "MRR", "nDCG"],
        risks=["poor chunking", "embedding domain mismatch", "hallucination"],
        first_experiment_note="Index the corpus with BM25 before dense retrieval.",
    ),
    "rag": MlPlanRules(
        baseline_models=["BM25", "Dense embedding retrieval"],
        metrics=["Recall@k", "MRR", "nDCG"],
        risks=["poor chunking", "embedding domain mismatch", "hallucination"],
        first_experiment_note="Validate retrieval quality before generation quality.",
    ),
    "recommendation": MlPlanRules(
        baseline_models=["Popularity baseline", "Matrix Factorization"],
        metrics=["Recall@k", "NDCG@k", "MRR"],
        risks=["cold start", "sparse interactions", "incorrect time-based split"],
        first_experiment_note="Build a popularity baseline with a time-aware split.",
    ),
    "forecasting": MlPlanRules(
        baseline_models=["Naive baseline", "ARIMA", "LightGBM"],
        metrics=["MAE", "RMSE", "MAPE"],
        risks=["time leakage", "distribution shift", "outliers"],
        first_experiment_note="Compare against a naive previous-value forecast.",
    ),
    "clustering": MlPlanRules(
        baseline_models=["K-Means", "DBSCAN"],
        metrics=["Silhouette Score", "Davies-Bouldin"],
        risks=["scale sensitivity", "choosing k", "noisy data"],
        first_experiment_note="Normalize features and run K-Means across several k values.",
    ),
    "anomaly_detection": MlPlanRules(
        baseline_models=["Isolation Forest", "Autoencoder"],
        metrics=["Precision@k", "Recall@k", "AUC-PR"],
        risks=["severe imbalance", "threshold selection", "false positive cost"],
        first_experiment_note="Start with Isolation Forest and explicit threshold review.",
    ),
}

GENERIC_RULES = MlPlanRules(
    baseline_models=["Simple baseline", "Strong classical baseline"],
    metrics=["primary metric", "secondary diagnostic metric"],
    risks=["data leakage", "overfitting", "unclear evaluation protocol"],
    first_experiment_note="Define a simple reproducible baseline before advanced models.",
    generic=True,
)


def rules_for_task(task_type: str | None) -> MlPlanRules:
    if not task_type:
        return GENERIC_RULES
    return RULE_MAP.get(task_type, GENERIC_RULES)
