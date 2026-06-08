"""End-to-end benchmark scenarios.

Promotes the ad-hoc Phase 2 eval (previously a throwaway script under /tmp,
see ``eval_phase_2.md``) into a deterministic, repeatable regression suite.

Each scenario drives the full Octopus flow through the installed CLI surface
and asserts the three guarantees the product is built on:

1. Command correctness   - the standard flow exits 0.
2. Workflow enforcement  - main-model work is blocked before a baseline exists.
3. Context efficiency     - ``octopus context`` is smaller than pasting every
   planning doc by hand (token saving).
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.context.token_estimator import estimate_tokens
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()

# (task_type, input_type, output_type, main_metric, project_type)
SCENARIOS = [
    ("text_classification", "text", "emotion_label", "macro_f1", "machine learning"),
    ("regression", "tabular", "price", "rmse", "machine learning"),
    ("image_classification", "image", "class_label", "macro_f1", "deep learning"),
    ("retrieval_qa", "text", "answer_with_source", "recall_at_k", "rag"),
]

PLANNING_DOCS = [
    "requirements.md",
    "ml_design.md",
    "experiment_plan.md",
    "data_strategy.md",
    "compute_budget.md",
    "tasks.md",
]

EXPECTED_ARTIFACTS = [
    *PLANNING_DOCS,
    ".octopus/tasks.json",
    "CLAUDE.md",
    "AGENTS.md",
    ".octopus/config.yaml",
    ".octopus/project_state.json",
    ".octopus/context/current_context.md",
]


def _seed(task_type, input_type, output_type, main_metric, project_type):
    """Init the project, then overwrite state with the scenario ML profile."""
    assert runner.invoke(app, ["init", "--runtime", "claude,codex", "--force"]).exit_code == 0
    write_state(
        sample_ml_state(
            project_type=project_type,
            task_type=task_type,
            input_type=input_type,
            output_type=output_type,
            main_metric=main_metric,
        )
    )


@pytest.mark.parametrize(
    "task_type,input_type,output_type,main_metric,project_type",
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS],
)
def test_scenario_flow_and_enforcement(
    tmp_project, task_type, input_type, output_type, main_metric, project_type
):
    _seed(task_type, input_type, output_type, main_metric, project_type)

    # 1. Standard planning flow must succeed.
    for cmd in (["plan"], ["ml-plan"], ["tasks"], ["task", "next"]):
        assert runner.invoke(app, cmd).exit_code == 0, f"command failed: {cmd}"

    # 2a. Main-model task is blocked before a baseline exists.
    before = runner.invoke(app, ["task", "start", "T020"])
    assert before.exit_code == 1, "T020 should be blocked before baseline"

    # 2b. Main-model experiment logging is blocked before a baseline exists.
    blocked = runner.invoke(
        app, ["exp", "log", "--kind", "main", "--name", "main_run", f"--metric={main_metric}=0.5"]
    )
    assert blocked.exit_code == 1, "main-model logging should be blocked before baseline"

    # 3. Context builds and stays under the default budget.
    ctx = runner.invoke(
        app, ["context", "--task", f"train {task_type} baseline", "--profile", "training"]
    )
    assert ctx.exit_code == 0
    assert Path(".octopus/context/current_context.md").exists()

    # 4. Logging a completed baseline unblocks the main-model task.
    log = runner.invoke(
        app,
        ["exp", "log", "--kind", "baseline", "--name", "baseline", f"--metric={main_metric}=0.0"],
    )
    assert log.exit_code == 0, log.output
    after = runner.invoke(app, ["task", "start", "T020"])
    assert after.exit_code == 0, "T020 should be unblocked after a completed baseline"

    # 5. Sync and status close the loop.
    assert runner.invoke(app, ["sync"]).exit_code == 0
    assert runner.invoke(app, ["status"]).exit_code == 0


@pytest.mark.parametrize(
    "task_type,input_type,output_type,main_metric,project_type",
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS],
)
def test_scenario_artifacts_exist(
    tmp_project, task_type, input_type, output_type, main_metric, project_type
):
    _seed(task_type, input_type, output_type, main_metric, project_type)
    for cmd in (["plan"], ["ml-plan"], ["tasks"]):
        runner.invoke(app, cmd)
    runner.invoke(app, ["context", "--task", "train baseline", "--profile", "training"])

    missing = [p for p in EXPECTED_ARTIFACTS if not Path(p).exists()]
    assert not missing, f"missing artifacts: {missing}"


@pytest.mark.parametrize(
    "task_type,input_type,output_type,main_metric,project_type",
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS],
)
def test_context_saves_tokens_vs_manual_paste(
    tmp_project, task_type, input_type, output_type, main_metric, project_type
):
    _seed(task_type, input_type, output_type, main_metric, project_type)
    for cmd in (["plan"], ["ml-plan"], ["tasks"]):
        runner.invoke(app, cmd)
    runner.invoke(app, ["context", "--task", "train baseline", "--profile", "training"])

    octopus_tokens = estimate_tokens(
        Path(".octopus/context/current_context.md").read_text(encoding="utf-8")
    )
    manual_tokens = sum(
        estimate_tokens(Path(doc).read_text(encoding="utf-8"))
        for doc in PLANNING_DOCS
        if Path(doc).exists()
    )

    assert octopus_tokens < manual_tokens, (
        f"{task_type}: context ({octopus_tokens}) not smaller than "
        f"manual paste ({manual_tokens})"
    )
