import json
from pathlib import Path

from typer.testing import CliRunner

from octopus.cli.main import app
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _init_ml_project():
    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    write_state(sample_ml_state())
    result = runner.invoke(app, ["tasks", "--force"])
    assert result.exit_code == 0


def _task_status(task_id: str) -> str:
    data = json.loads(Path(".octopus/tasks.json").read_text(encoding="utf-8"))
    return next(task["status"] for task in data["tasks"] if task["id"] == task_id)


def test_task_start_blocks_main_model_until_baseline_logged(tmp_project):
    _init_ml_project()

    result = runner.invoke(app, ["task", "start", "T020"])

    assert result.exit_code == 1
    assert "Task T020 is blocked" in result.output
    assert "T012" in result.output
    assert "octopus exp log --kind baseline" in result.output


def test_task_done_t012_requires_real_baseline_experiment(tmp_project):
    _init_ml_project()

    result = runner.invoke(app, ["task", "done", "T012"])

    assert result.exit_code == 1
    assert "Cannot complete T012" in result.output
    assert _task_status("T012") == "todo"


def test_baseline_experiment_marks_baseline_tasks_done(tmp_project):
    _init_ml_project()

    result = runner.invoke(
        app,
        [
            "exp",
            "log",
            "--kind",
            "baseline",
            "--name",
            "tfidf_baseline",
            "--model",
            "TF-IDF + Logistic Regression",
            "--metric",
            "macro_f1=0.58",
        ],
    )

    assert result.exit_code == 0
    assert _task_status("T010") == "done"
    assert _task_status("T011") == "done"
    assert _task_status("T012") == "done"
    assert "[x] T012" in Path("tasks.md").read_text(encoding="utf-8")


def test_task_next_points_to_first_unblocked_task(tmp_project):
    _init_ml_project()

    result = runner.invoke(app, ["task", "next"])

    assert result.exit_code == 0
    assert "T001" in result.output
    assert "octopus task start T001" in result.output


def test_tasks_use_selected_baseline_model(tmp_project):
    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    write_state(sample_ml_state(baseline_model="TF-IDF + LinearSVC"))

    result = runner.invoke(app, ["tasks", "--force"])

    assert result.exit_code == 0
    assert "Implement baseline model (TF-IDF + LinearSVC)" in Path("tasks.md").read_text(
        encoding="utf-8"
    )
