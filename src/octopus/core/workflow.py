from octopus.core.schemas import ExperimentRecord, ProjectState
from octopus.storage.experiment_store import list_experiments

ExperimentKind = str

BASELINE_HINTS = (
    "baseline",
    "tf-idf",
    "tfidf",
    "linear regression",
    "linearsvc",
    "linear svc",
    "logistic regression",
    "bm25",
    "simple tree",
)
MAIN_MODEL_HINTS = (
    "main",
    "candidate",
    "phobert",
    "bert",
    "transformer",
    "resnet",
    "mobilenet",
    "efficientnet",
    "finetune",
    "fine-tune",
    "llm",
    "reranker",
)


def infer_experiment_kind(name: str, model: str | None, explicit_kind: str = "auto") -> str:
    if explicit_kind != "auto":
        return explicit_kind
    text = f"{name} {model or ''}".lower()
    if any(hint in text for hint in BASELINE_HINTS):
        return "baseline"
    if any(hint in text for hint in MAIN_MODEL_HINTS):
        return "main"
    return "other"


def is_baseline_experiment(record: ExperimentRecord) -> bool:
    return infer_experiment_kind(record.name, record.model, record.kind) == "baseline"


def has_completed_baseline() -> bool:
    return any(
        record.status == "completed" and is_baseline_experiment(record)
        for record in list_experiments()
    )


def requires_baseline_gate(state: ProjectState) -> bool:
    return state.baseline_required and state.project_type in {
        "machine learning",
        "deep learning",
        "rag",
    }
