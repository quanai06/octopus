from octopus.core.schemas import ProjectState
from octopus.storage.state_store import save_state


def sample_ml_state(**updates):
    data = {
        "project_name": "Vietnamese Emotion Classifier",
        "project_goal": "Classify Vietnamese social posts by emotion.",
        "target_users": "ML engineers",
        "project_type": "ml",
        "task_type": "text_classification",
        "input_type": "text",
        "output_type": "emotion_label",
        "dataset_status": "available",
        "dataset_size_note": "~50k samples",
        "has_labels": True,
        "has_class_imbalance": True,
        "main_metric": "macro_f1",
        "target_score": 0.82,
        "runtime": ["claude", "codex"],
        "compute": {"has_gpu": True, "environment": "colab_t4"},
    }
    data.update(updates)
    return ProjectState.model_validate(data)


def write_state(state: ProjectState | None = None):
    save_state(state or sample_ml_state())
