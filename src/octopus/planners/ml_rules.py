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
        metrics=["Recall@k", "MRR", "nDCG", "source hit rate", "faithfulness"],
        risks=[
            "poor chunking",
            "embedding domain mismatch",
            "missing source citations",
            "hallucination",
        ],
        first_experiment_note="Index the corpus with BM25 before dense retrieval.",
        problem_type="retrieval_ranking",
        first_experiments=(
            "Create a small labeled query-document evaluation set.",
            "Run BM25 baseline.",
            "Run dense retrieval baseline.",
            "Verify returned answers include cited source documents.",
            "Compare Recall@k and inspect failure queries.",
        ),
        data_checks=(
            "Validate document chunking boundaries.",
            "Check duplicate documents and stale content.",
            "Confirm query labels match the target user intent.",
            "Require answer citations that point to retrieved source chunks.",
        ),
    ),
    "rag": MlPlanRules(
        baseline_models=["BM25", "Dense embedding retrieval"],
        metrics=["Recall@k", "MRR", "nDCG", "source hit rate", "faithfulness"],
        risks=[
            "poor chunking",
            "embedding domain mismatch",
            "missing source citations",
            "hallucination",
        ],
        first_experiment_note="Validate retrieval quality before generation quality.",
        problem_type="retrieval_augmented_generation",
        first_experiments=(
            "Build retrieval-only evaluation set.",
            "Run BM25 baseline.",
            "Run dense retrieval baseline.",
            "Check every generated answer has a cited source chunk.",
            "Only evaluate generation after retrieval reaches the target Recall@k.",
        ),
        data_checks=(
            "Validate source document freshness and ownership.",
            "Check chunk size and overlap against answer boundaries.",
            "Separate retrieval metrics from generation metrics.",
            "Require source citations and faithfulness checks for generated answers.",
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


# Data-type-aware standard train/eval protocol for the baseline. The point is a
# *rigorous* baseline (correct split + cross-validation + leakage-safe
# preprocessing + variance reporting), not a single random holdout.
_CLASSIFICATION_PROTOCOL = (
    "Hold out a stratified test set first; keep it untouched until final reporting.",
    "Use StratifiedKFold (k=5, fixed seed) on the train+validation pool for model selection.",
    "Report mean ± std of macro_f1 and per-class recall across folds, not a single split.",
    "Fit all preprocessing (vectorizer/scaler/encoder) inside each fold on train folds only.",
    "If samples share a group/author/source, use StratifiedGroupKFold to avoid leakage.",
    "For deep models where k-fold is too costly, use a fixed stratified split with >=3 seeds "
    "and still report mean ± std.",
)
_REGRESSION_PROTOCOL = (
    "Hold out a test set; never tune on it.",
    "Use KFold (k=5, fixed seed) for model selection; GroupKFold if rows share an entity.",
    "If the target is time-ordered, use a temporal split / TimeSeriesSplit, not random KFold.",
    "Report mean ± std of RMSE/MAE across folds and inspect residuals by segment.",
    "Fit scalers/encoders inside each fold on train folds only.",
)
_TIMESERIES_PROTOCOL = (
    "Use a temporal split: train on the past, validate/test on the most recent window. "
    "Never shuffle.",
    "Backtest with TimeSeriesSplit (expanding or rolling window, n_splits=5).",
    "Compute lag/rolling features inside each fold; never use future information.",
    "Compare against a naive previous-value / seasonal-naive baseline.",
    "Report MAE/RMSE/MAPE per fold (mean ± std) and on the final holdout horizon.",
)
_RETRIEVAL_PROTOCOL = (
    "Build a fixed labeled query -> relevant-document evaluation set and freeze it.",
    "Evaluate retrieval first: Recall@k, MRR, and source-hit rate on the fixed query set.",
    "Use a fixed dev/test query split (or k-fold over queries) for stable estimates; "
    "never tune on test queries.",
    "Chunk once with recorded size/overlap; fit nothing on the eval queries.",
    "Only evaluate generation after retrieval reaches the target Recall@k; require source "
    "citations (faithfulness).",
)
_RECOMMENDATION_PROTOCOL = (
    "Use a time-aware split: train on past interactions, test on future ones. No random split.",
    "Evaluate Recall@k / NDCG@k / MRR on held-out future interactions.",
    "Guard cold-start users/items and leakage of future interactions into training.",
)
DEFAULT_EVAL_PROTOCOL = (
    "Hold out a test set and keep it untouched until final reporting.",
    "Use k-fold cross-validation (k=5, fixed seed) for model selection, with the fold scheme "
    "that matches the data: StratifiedKFold for classification, KFold for tabular regression, "
    "TimeSeriesSplit for time-ordered data, GroupKFold when rows share an entity.",
    "Fit all preprocessing inside each fold on the training folds only.",
    "Report mean ± std of the main metric across folds, then confirm on the held-out test set.",
)

_EVAL_PROTOCOLS: dict[str, tuple[str, ...]] = {
    "text_classification": _CLASSIFICATION_PROTOCOL,
    "image_classification": _CLASSIFICATION_PROTOCOL,
    "regression": _REGRESSION_PROTOCOL,
    "forecasting": _TIMESERIES_PROTOCOL,
    "retrieval": _RETRIEVAL_PROTOCOL,
    "rag": _RETRIEVAL_PROTOCOL,
    "recommendation": _RECOMMENDATION_PROTOCOL,
}


def evaluation_protocol_for(task_type: str | None) -> list[str]:
    """Return the standard train/eval protocol for the task's data type."""
    if not task_type:
        return list(DEFAULT_EVAL_PROTOCOL)
    return list(_EVAL_PROTOCOLS.get(task_type, DEFAULT_EVAL_PROTOCOL))
