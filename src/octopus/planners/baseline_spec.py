from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.paths import BASELINE_SPEC_YAML
from octopus.core.schemas import ProjectState
from octopus.planners.ml_planner import selected_baseline_models
from octopus.planners.ml_rules import rules_for_task

DATA_EXTENSIONS = (".csv", ".tsv", ".xlsx", ".xls", ".jsonl", ".parquet")


def _find_split_file(names: tuple[str, ...]) -> str | None:
    candidates: list[Path] = []
    for path in Path(".").iterdir():
        if not path.is_file() or path.suffix.lower() not in DATA_EXTENSIONS:
            continue
        lower = path.name.lower()
        if any(name in lower for name in names):
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (len(item.name), item.name))
    return candidates[0].as_posix()


def _baseline_slug(model: str | None) -> str:
    normalized = (model or "").lower()
    if "tf-idf" in normalized or "tfidf" in normalized:
        if "svm" in normalized or "svc" in normalized:
            return "tfidf_linearsvc"
        if "nb" in normalized or "bayes" in normalized:
            return "tfidf_nb"
        return "tfidf_logreg"
    return normalized.replace(" ", "_").replace("+", "").replace("/", "_") or "baseline"


def baseline_spec_payload(state: ProjectState) -> dict[str, Any]:
    rules = rules_for_task(state.task_type if state.task_type != "rag" else "rag")
    baseline_model = selected_baseline_models(state, rules)[0]
    fixed_split = state.fixed_split_available
    payload: dict[str, Any] = {
        "task": state.task_type or state.project_type,
        "input_type": state.input_type,
        "output_type": state.output_type,
        "metric": state.main_metric or rules.metrics[0],
        "no_test_tuning": True,
        "data": {
            "status": state.dataset_status or "unknown",
            "fixed_split": fixed_split,
            "train": _find_split_file(("train",)),
            "valid": _find_split_file(("valid", "val", "dev")),
            "test": _find_split_file(("test",)),
            "note": state.dataset_size_note,
        },
        "baseline": {
            "model": _baseline_slug(baseline_model),
            "display_name": baseline_model,
            "cv_folds": 0 if fixed_split else 5,
            "final_train": "train_valid" if fixed_split else "train",
        },
        "artifacts": {
            "run_dir": "runs/baseline",
            "save_model": True,
            "save_metrics": True,
            "save_predictions": True,
            "save_manifest": True,
        },
    }
    if state.task_type == "text_classification":
        payload["text"] = {
            "text_col": "Sentence",
            "label_col": "Emotion",
            "unicode_normalize": True,
            "normalize_urls_mentions": True,
            "char_ngrams": True,
        }
    return payload


def render_baseline_spec(state: ProjectState, *, backup: bool = True) -> Path:
    if backup:
        backup_if_exists(BASELINE_SPEC_YAML)
    content = yaml.safe_dump(baseline_spec_payload(state), sort_keys=False, allow_unicode=True)
    atomic_write_text(BASELINE_SPEC_YAML, content)
    return BASELINE_SPEC_YAML
