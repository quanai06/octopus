from dataclasses import dataclass


@dataclass(frozen=True)
class MlPlanRules:
    baseline_models: list[str]
    metrics: list[str]
    risks: list[str]
    first_experiment_note: str
    generic: bool = False
    problem_type: str = "to_be_defined"
    first_experiments: tuple[str, ...] = ()
    data_checks: tuple[str, ...] = ()
    training_checklist: tuple[str, ...] = ()


RULE_MAP: dict[str, MlPlanRules] = {
    "text_classification": MlPlanRules(
        baseline_models=["TF-IDF + Logistic Regression", "TF-IDF + LinearSVC"],
        metrics=["macro_f1", "per-class recall", "confusion matrix"],
        risks=["class imbalance", "noisy text", "data leakage", "overfitting"],
        first_experiment_note="Train a TF-IDF + Logistic Regression baseline.",
        problem_type="supervised_classification",
        first_experiments=(
            "Inspect label distribution and text length distribution.",
            "Train TF-IDF + LinearSVC baseline.",
            "Train transformer classifier without augmentation.",
            "Add class weights if minority recall is weak.",
            "Compare macro F1 and confusion matrix against the baseline.",
        ),
        data_checks=(
            "Verify label taxonomy and remove ambiguous labels before training.",
            "Use stratified train / validation / test split.",
            "Scan for duplicate or near-duplicate text across splits.",
            "Inspect noisy text, slang, casing, URLs, emojis, and teencode.",
        ),
        training_checklist=(
            "Freeze the split before model comparison.",
            "Log macro F1, per-class recall, confusion matrix, and seed.",
            "Keep preprocessing identical between baseline and transformer runs.",
        ),
    ),
    "image_classification": MlPlanRules(
        baseline_models=["Pretrained ResNet", "MobileNet"],
        metrics=["accuracy", "macro_f1 if imbalanced"],
        risks=["incorrect augmentation", "train/val leakage", "class imbalance"],
        first_experiment_note="Fine-tune a small pretrained CNN baseline.",
        problem_type="supervised_classification",
        first_experiments=(
            "Inspect class distribution and image sizes.",
            "Fine-tune MobileNet or ResNet baseline.",
            "Add augmentation only after the no-augmentation baseline.",
        ),
        data_checks=(
            "Check duplicate images across splits.",
            "Validate labels manually on a small random sample.",
            "Use stratified split when labels are imbalanced.",
        ),
    ),
    "regression": MlPlanRules(
        baseline_models=["Linear Regression", "Random Forest", "LightGBM"],
        metrics=["MAE", "RMSE", "R2"],
        risks=["outliers", "data leakage", "target skew"],
        first_experiment_note="Train Linear Regression and compare with a tree baseline.",
        problem_type="supervised_regression",
        first_experiments=(
            "Inspect target distribution and outliers.",
            "Train Linear Regression baseline.",
            "Train tree baseline and compare residuals.",
        ),
        data_checks=(
            "Check target leakage columns.",
            "Use a split that matches deployment time or grouping constraints.",
            "Review residuals by important segments.",
        ),
    ),
    "retrieval": MlPlanRules(
        baseline_models=["BM25", "Dense embedding retrieval"],
        metrics=["Recall@k", "MRR", "nDCG"],
        risks=["poor chunking", "embedding domain mismatch", "hallucination"],
        first_experiment_note="Index the corpus with BM25 before dense retrieval.",
        problem_type="retrieval_ranking",
        first_experiments=(
            "Create a small labeled query-document evaluation set.",
            "Run BM25 baseline.",
            "Run dense retrieval baseline.",
            "Compare Recall@k and inspect failure queries.",
        ),
        data_checks=(
            "Validate document chunking boundaries.",
            "Check duplicate documents and stale content.",
            "Confirm query labels match the target user intent.",
        ),
    ),
    "rag": MlPlanRules(
        baseline_models=["BM25", "Dense embedding retrieval"],
        metrics=["Recall@k", "MRR", "nDCG"],
        risks=["poor chunking", "embedding domain mismatch", "hallucination"],
        first_experiment_note="Validate retrieval quality before generation quality.",
        problem_type="retrieval_augmented_generation",
        first_experiments=(
            "Build retrieval-only evaluation set.",
            "Run BM25 baseline.",
            "Run dense retrieval baseline.",
            "Only evaluate generation after retrieval reaches the target Recall@k.",
        ),
        data_checks=(
            "Validate source document freshness and ownership.",
            "Check chunk size and overlap against answer boundaries.",
            "Separate retrieval metrics from generation metrics.",
        ),
    ),
    "recommendation": MlPlanRules(
        baseline_models=["Popularity baseline", "Matrix Factorization"],
        metrics=["Recall@k", "NDCG@k", "MRR"],
        risks=["cold start", "sparse interactions", "incorrect time-based split"],
        first_experiment_note="Build a popularity baseline with a time-aware split.",
        problem_type="ranking_recommendation",
    ),
    "forecasting": MlPlanRules(
        baseline_models=["Naive baseline", "ARIMA", "LightGBM"],
        metrics=["MAE", "RMSE", "MAPE"],
        risks=["time leakage", "distribution shift", "outliers"],
        first_experiment_note="Compare against a naive previous-value forecast.",
        problem_type="time_series_forecasting",
    ),
    "clustering": MlPlanRules(
        baseline_models=["K-Means", "DBSCAN"],
        metrics=["Silhouette Score", "Davies-Bouldin"],
        risks=["scale sensitivity", "choosing k", "noisy data"],
        first_experiment_note="Normalize features and run K-Means across several k values.",
        problem_type="unsupervised_clustering",
    ),
    "anomaly_detection": MlPlanRules(
        baseline_models=["Isolation Forest", "Autoencoder"],
        metrics=["Precision@k", "Recall@k", "AUC-PR"],
        risks=["severe imbalance", "threshold selection", "false positive cost"],
        first_experiment_note="Start with Isolation Forest and explicit threshold review.",
        problem_type="anomaly_detection",
    ),
}

GENERIC_RULES = MlPlanRules(
    baseline_models=["Simple baseline", "Strong classical baseline"],
    metrics=["primary metric", "secondary diagnostic metric"],
    risks=["data leakage", "overfitting", "unclear evaluation protocol"],
    first_experiment_note="Define a simple reproducible baseline before advanced models.",
    generic=True,
    first_experiments=(
        "Define the evaluation protocol.",
        "Train the simplest reproducible baseline.",
        "Review errors before selecting a larger model.",
    ),
    data_checks=(
        "Confirm dataset source, labels, and split strategy.",
        "Check for leakage and duplicate samples.",
    ),
)


def rules_for_task(task_type: str | None) -> MlPlanRules:
    if not task_type:
        return GENERIC_RULES
    return RULE_MAP.get(task_type, GENERIC_RULES)
