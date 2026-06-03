from pathlib import Path

import pytest

from octopus.cli.commands.ml_plan import generate_ml_plan
from tests.helpers import sample_ml_state, write_state


def test_ml_plan_text_classification_baseline(tmp_project):
    write_state()
    generate_ml_plan(force=True)

    assert "TF-IDF + Logistic Regression" in Path("ml_design.md").read_text(encoding="utf-8")


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
