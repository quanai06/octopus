from pathlib import Path

import pytest

from octopus.cli.commands.ml_plan import generate_ml_plan
from tests.helpers import sample_ml_state, write_state


def test_ml_plan_text_classification_baseline(tmp_project):
    write_state()
    generate_ml_plan(force=True)

    assert "TF-IDF + Logistic Regression" in Path("ml_design.md").read_text(encoding="utf-8")


def test_ml_plan_uses_selected_baseline_first(tmp_project):
    write_state(sample_ml_state(baseline_model="TF-IDF + LinearSVC"))
    generate_ml_plan(force=True)

    ml_design = Path("ml_design.md").read_text(encoding="utf-8")
    experiment_plan = Path("experiment_plan.md").read_text(encoding="utf-8")

    assert ml_design.find("- TF-IDF + LinearSVC") < ml_design.find(
        "- TF-IDF + Logistic Regression"
    )
    assert "- Model: TF-IDF + LinearSVC" in experiment_plan
    assert "Train TF-IDF + LinearSVC baseline." in experiment_plan


def test_ml_plan_text_classification_metrics(tmp_project):
    write_state()
    generate_ml_plan(force=True)

    assert "macro_f1" in Path("ml_design.md").read_text(encoding="utf-8")


def test_ml_plan_regression_baseline(tmp_project):
    write_state(sample_ml_state(task_type="regression", main_metric="RMSE"))
    generate_ml_plan(force=True)

    assert "Linear Regression" in Path("ml_design.md").read_text(encoding="utf-8")


def test_ml_plan_retrieval_baseline(tmp_project):
    write_state(sample_ml_state(task_type="retrieval", main_metric="Recall@k"))
    generate_ml_plan(force=True)

    assert "BM25" in Path("ml_design.md").read_text(encoding="utf-8")


def test_ml_plan_unknown_task_type_uses_generic(tmp_project):
    write_state(sample_ml_state(task_type="custom_problem"))
    generate_ml_plan(force=True)

    assert "Simple baseline" in Path("ml_design.md").read_text(encoding="utf-8")


def test_ml_plan_fails_for_software_project(tmp_project):
    write_state(sample_ml_state(project_type="software", task_type=None))

    with pytest.raises(SystemExit) as exc:
        generate_ml_plan(force=True)

    assert exc.value.code == 0
    assert not Path("ml_design.md").exists()


def test_ml_plan_generates_both_files(tmp_project):
    write_state()
    generate_ml_plan(force=True)

    assert Path("ml_design.md").exists()
    assert Path("experiment_plan.md").exists()


def test_ml_plan_generates_phase_2_artifacts(tmp_project):
    write_state()
    generate_ml_plan(force=True)

    assert Path("data_strategy.md").exists()
    assert Path("compute_budget.md").exists()


def test_ml_plan_vietnamese_text_classification_candidates(tmp_project):
    write_state(
        sample_ml_state(
            project_goal="Train model phân loại cảm xúc tiếng Việt bằng PhoBERT.",
            task_type="text_classification",
            main_metric="macro_f1",
        )
    )
    generate_ml_plan(force=True)

    ml_design = Path("ml_design.md").read_text(encoding="utf-8")
    experiment_plan = Path("experiment_plan.md").read_text(encoding="utf-8")

    assert "supervised_classification" in ml_design
    assert "Vietnamese" in ml_design
    assert "vinai/phobert-base" in ml_design
    assert "per-class recall" in ml_design
    assert "Experiment 3: Candidate model" in experiment_plan
    assert "Stop if macro_f1 does not improve after 3 controlled experiments." in experiment_plan
