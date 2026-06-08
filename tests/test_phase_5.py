import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.experiments.baseline_profile import NoBaselineError, profile_baseline
from octopus.experiments.technique_library import (
    DOMAIN_CLASSIFICATION,
    DOMAIN_RAG,
    DOMAIN_REGRESSION,
    SYMPTOM_CLASS_IMBALANCE,
    SYMPTOM_LOW_RETRIEVAL,
    SYMPTOM_OVERFITTING,
    antipatterns_for,
    domain_for,
    techniques_for,
)
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


# --- technique library (pure unit tests) -----------------------------------


def test_domain_for_maps_task_and_project_types():
    assert domain_for("text_classification") == DOMAIN_CLASSIFICATION
    assert domain_for("image_classification") == DOMAIN_CLASSIFICATION
    assert domain_for("regression") == DOMAIN_REGRESSION
    assert domain_for("retrieval_qa") == DOMAIN_RAG
    assert domain_for(None, project_type="rag") == DOMAIN_RAG
    assert domain_for("something_unknown") == "generic"


def test_techniques_for_filters_by_domain_and_symptom():
    techniques = techniques_for(DOMAIN_CLASSIFICATION, [SYMPTOM_CLASS_IMBALANCE])
    ids = {technique.technique_id for technique in techniques}
    assert "cls_class_weights" in ids
    # RAG-only techniques must not leak into a classification domain.
    assert "rag_chunking" not in ids
    # Every returned technique must actually target the requested symptom.
    assert all(SYMPTOM_CLASS_IMBALANCE in technique.symptoms for technique in techniques)


def test_techniques_for_ranks_cheap_low_risk_first():
    techniques = techniques_for(DOMAIN_CLASSIFICATION, [SYMPTOM_CLASS_IMBALANCE])
    assert techniques, "expected at least one technique"
    # The top suggestion should be low cost and low risk (class-weighted loss).
    assert techniques[0].cost == "low"
    assert techniques[0].risk == "low"


def test_techniques_for_respects_limit():
    techniques = techniques_for(DOMAIN_CLASSIFICATION, [SYMPTOM_CLASS_IMBALANCE], limit=2)
    assert len(techniques) <= 2


def test_rag_low_retrieval_returns_retrieval_techniques():
    ids = {t.technique_id for t in techniques_for(DOMAIN_RAG, [SYMPTOM_LOW_RETRIEVAL])}
    assert {"rag_chunking", "rag_hybrid"} & ids


def test_antipatterns_for_overfitting():
    names = {anti.name for anti in antipatterns_for([SYMPTOM_OVERFITTING])}
    assert "Train for more epochs" in names


# --- baseline profile end to end -------------------------------------------


def _init(**state_updates) -> None:
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    write_state(sample_ml_state(**state_updates))


def _ingest_imbalanced_baseline() -> None:
    run_dir = Path("runs/E001")
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text(
        json.dumps({"macro_f1": 0.62, "accuracy": 0.85, "train_loss": 0.30, "val_loss": 0.61}),
        encoding="utf-8",
    )
    (run_dir / "classification_report.json").write_text(
        json.dumps(
            {
                "fear": {"precision": 0.5, "recall": 0.38, "f1-score": 0.43, "support": 110},
                "joy": {"precision": 0.9, "recall": 0.93, "f1-score": 0.91, "support": 980},
                "macro avg": {"precision": 0.7, "recall": 0.65, "f1-score": 0.62},
            }
        ),
        encoding="utf-8",
    )
    runner.invoke(app, ["exp", "ingest", "--run-dir", str(run_dir), "--kind", "baseline"])


def test_profile_command_writes_report_and_recommends_imbalance_fix(tmp_project):
    _init(target_score=0.82, main_metric="macro_f1")
    _ingest_imbalanced_baseline()

    result = runner.invoke(app, ["exp", "profile"])

    assert result.exit_code == 0, result.output
    report = Path(".octopus/reports/baseline_profile.md")
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "# Baseline Profile - E001" in content
    assert "Class-weighted loss" in content
    assert "## 6. Do Not Try Yet" in content
    # Imbalance anti-pattern should be surfaced.
    assert "bigger backbone" in content.lower()


def test_profile_object_has_expected_diagnosis(tmp_project):
    _init(target_score=0.82, main_metric="macro_f1")
    _ingest_imbalanced_baseline()

    profile = profile_baseline()

    assert profile.experiment_id == "E001"
    assert profile.domain == DOMAIN_CLASSIFICATION
    assert profile.main_metric == "macro_f1"
    assert profile.target_gap is not None and round(profile.target_gap, 2) == 0.20
    assert profile.headroom == "large"
    assert SYMPTOM_CLASS_IMBALANCE in profile.detected_symptoms
    assert any(w.label == "fear" for w in profile.weak_classes)
    assert profile.recommended_techniques
    assert profile.readiness == "ready_to_tune"


def test_profile_flags_metric_gap_as_data_quality_risk(tmp_project):
    _init(target_score=0.82, main_metric="macro_f1")
    _ingest_imbalanced_baseline()

    profile = profile_baseline()

    assert any("macro F1" in flag for flag in profile.data_quality_flags)


def test_profile_without_baseline_exits_nonzero(tmp_project):
    _init()

    result = runner.invoke(app, ["exp", "profile"])

    assert result.exit_code == 1
    assert "baseline" in result.output.lower()


def test_profile_baseline_raises_without_baseline(tmp_project):
    _init()
    try:
        profile_baseline()
    except NoBaselineError:
        pass
    else:  # pragma: no cover - guard
        raise AssertionError("expected NoBaselineError")


# --- next_planner now draws from the technique library ---------------------


def test_next_imbalance_direction_cites_library_techniques(tmp_project):
    _init(target_score=0.82, main_metric="macro_f1")
    _ingest_imbalanced_baseline()
    runner.invoke(app, ["exp", "analyze", "E001"])

    result = runner.invoke(app, ["exp", "next", "--top-k", "3"])

    assert result.exit_code == 0, result.output
    data = yaml.safe_load(
        Path(".octopus/plans/next_steps.yaml").read_text(encoding="utf-8")
    )
    first = data["directions"][0]
    assert first["direction_id"] == "D1"
    assert "minority recall" in first["title"].lower()
    assert first["recommendation"] == "recommended"
    # The rationale must now name concrete techniques pulled from the library.
    assert "Suggested techniques" in first["rationale"]
    assert "Class-weighted loss" in first["rationale"]


def test_next_rag_recommends_retrieval_direction(tmp_project):
    _init(project_type="rag", task_type="retrieval_qa", main_metric="recall_at_k", target_score=0.8)
    run_dir = Path("runs/E001")
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text(
        '{"recall_at_k": 0.42, "mrr": 0.38}', encoding="utf-8"
    )
    runner.invoke(app, ["exp", "ingest", "--run-dir", str(run_dir), "--kind", "baseline"])

    result = runner.invoke(app, ["exp", "next"])

    assert result.exit_code == 0, result.output
    data = yaml.safe_load(
        Path(".octopus/plans/next_steps.yaml").read_text(encoding="utf-8")
    )
    first = data["directions"][0]
    assert "retrieval" in first["title"].lower()
    assert first["recommendation"] == "recommended"
