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


def test_context_uses_training_profile_sections(tmp_project):
    state = _write_plan_files()
    content, result = build_context(state, "train PhoBERT baseline", profile="training")

    assert result.profile == "training"
    assert "Selected Planning Context" in content
    assert any("experiment_plan.md#" in section for section in result.included_sections)
    assert "Functional Requirements" not in content


def test_context_minimal_baseline_profile_is_smaller(tmp_project):
    state = _write_plan_files()
    training_content, training = build_context(
        state, "train TF-IDF baseline", profile="training"
    )
    minimal_content, minimal = build_context(
        state, "train TF-IDF baseline", profile="minimal-baseline", token_budget=1200
    )

    assert minimal.profile == "minimal-baseline"
    assert minimal.estimated_tokens < training.estimated_tokens
    assert len(minimal_content) < len(training_content)


def test_context_full_includes_review_sections(tmp_project):
    state = _write_plan_files()
    content, result = build_context(state, "review project", full=True)

    assert result.profile == "full"
    assert "requirements.md#Functional Requirements" in result.included_sections
    assert "## Functional Requirements" in content


def test_context_budget_skips_low_priority_sections(tmp_project):
    state = _write_plan_files()
    _, result = build_context(
        state,
        "train TF-IDF baseline",
        profile="training",
        token_budget=200,
    )

    assert result.skipped_sections


def test_context_reports_over_budget_when_fixed_overhead_exceeds_budget(tmp_project):
    state = _write_plan_files()
    _, result = build_context(
        state,
        "train TF-IDF baseline",
        profile="training",
        token_budget=50,
    )

    assert result.token_status == "over_budget"


def test_context_includes_relevant_code_files(tmp_project):
    state = _write_plan_files()
    Path("src").mkdir()
    Path("src/train_baseline.py").write_text(
        "\n".join(
            [
                "def train_baseline(dataset):",
                "    model = 'TF-IDF + Logistic Regression'",
                "    return model, dataset",
            ]
        ),
        encoding="utf-8",
    )

    content, result = build_context(state, "train baseline model", profile="training")

    assert "## Relevant Code Context" in content
    assert "src/train_baseline.py" in result.included_files
    assert "train_baseline" in content
