from pathlib import Path

from octopus.context.builder import build_context
from octopus.context.file_scanner import scan_project_files
from octopus.context.token_estimator import get_token_status
from octopus.core.paths import CURRENT_CONTEXT
from octopus.planners.ml_planner import render_ml_plan
from octopus.planners.requirement_planner import render_requirements
from octopus.planners.task_planner import render_tasks
from tests.helpers import sample_ml_state, write_state


def _write_plan_files(state=None):
    state = state or sample_ml_state()
    write_state(state)
    render_requirements(state, backup=False)
    render_ml_plan(state, backup=False)
    render_tasks(state, backup=False)
    return state


def test_context_creates_output_file(tmp_project):
    state = _write_plan_files()
    _, result = build_context(state, "train TF-IDF baseline")

    assert CURRENT_CONTEXT.exists()
    assert result.output_path == ".octopus/context/current_context.md"


def test_context_excludes_venv(tmp_project):
    Path(".venv/bin").mkdir(parents=True)
    Path(".venv/bin/python").write_text("", encoding="utf-8")

    included, _, _ = scan_project_files()

    assert ".venv/bin/python" not in included


def test_context_excludes_data_dir(tmp_project):
    Path("data").mkdir()
    Path("data/train.csv").write_text("x", encoding="utf-8")

    included, _, _ = scan_project_files()

    assert "data/train.csv" not in included


def test_context_excludes_checkpoint_files(tmp_project):
    Path("model.pt").write_text("x", encoding="utf-8")

    included, _, _ = scan_project_files()

    assert "model.pt" not in included


def test_context_estimates_tokens_gt_zero(tmp_project):
    state = _write_plan_files()
    _, result = build_context(state, "train TF-IDF baseline")

    assert result.estimated_tokens > 0


def test_context_token_status_warning():
    assert get_token_status(8_000) == "warning"


def test_context_token_status_exceeded():
    assert get_token_status(16_000) == "exceeded"


def test_context_includes_task_name(tmp_project):
    state = _write_plan_files()
    build_context(state, "train TF-IDF baseline")

    assert "train TF-IDF baseline" in CURRENT_CONTEXT.read_text(encoding="utf-8")
