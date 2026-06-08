import json
from pathlib import Path

from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.install.artifacts import AGENT_DEFS, render_agent_def
from octopus.install.installer import install
from octopus.storage.session_store import (
    load_session,
    record_if_active,
    session_active,
    start_session,
)
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _init() -> None:
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    write_state(sample_ml_state())


# --- session store ---------------------------------------------------------


def test_start_session_writes_state_and_md(tmp_project):
    _init()
    result = runner.invoke(app, ["session", "start", "--goal", "beat the baseline"])
    assert result.exit_code == 0
    assert Path(".octopus/session/current.json").exists()
    md = Path(".octopus/session/current.md").read_text(encoding="utf-8")
    assert "beat the baseline" in md
    state = load_session()
    assert state is not None and state.status == "active"


def test_log_event_appends_and_updates_fields(tmp_project):
    _init()
    start_session(goal="g")
    record_if_active("direction", "chose D1", selected_direction="D1")
    state = load_session()
    assert state is not None
    assert state.selected_direction == "D1"
    assert state.events[-1].kind == "direction"


def test_record_if_active_is_noop_without_session(tmp_project):
    _init()
    assert session_active() is False
    record_if_active("note", "nothing should happen")
    assert load_session() is None


def test_end_session_archives(tmp_project):
    _init()
    state = start_session()
    runner.invoke(app, ["session", "end"])
    assert Path(f".octopus/session/{state.session_id}.json").exists()
    ended = load_session()
    assert ended is not None and ended.status == "ended"


# --- auto-capture from other commands --------------------------------------


def test_task_start_records_into_session(tmp_project):
    _init()
    runner.invoke(app, ["plan"])
    runner.invoke(app, ["ml-plan"])
    runner.invoke(app, ["tasks"])
    start_session()

    started = runner.invoke(app, ["task", "start", "T001"])
    assert started.exit_code == 0, started.output

    state = load_session()
    assert state is not None
    assert state.current_task and "T001" in state.current_task


def test_resume_reports_active_session(tmp_project):
    _init()
    start_session(goal="restore me")
    record_if_active("note", "did a thing")

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    assert "restore me" in result.output
    assert "current_context.md" in result.output


# --- agent definitions installed -------------------------------------------


def test_agent_defs_render_with_frontmatter():
    assert AGENT_DEFS, "expected agent definitions in Phase 4"
    rendered = render_agent_def(AGENT_DEFS[0])
    assert rendered.startswith("---")
    assert "name: octopus-baseline-runner" in rendered
    assert "model: inherit" in rendered


def test_install_writes_agent_files(tmp_path):
    install(["claude"], home=tmp_path)
    agents = tmp_path / ".claude" / "agents"
    names = {p.name for p in agents.glob("*.md")}
    assert "octopus-baseline-runner.md" in names
    assert "octopus-rag-evaluator.md" in names


def test_resume_command_router_installed(tmp_path):
    install(["claude"], home=tmp_path)
    assert (tmp_path / ".claude" / "commands" / "octopus-resume.md").exists()


def test_install_manifest_lists_agents(tmp_path):
    install(["claude"], home=tmp_path)
    manifest = json.loads(
        (tmp_path / ".claude" / ".octopus-manifest.json").read_text(encoding="utf-8")
    )
    assert any("agents/octopus-tuner.md" in f for f in manifest["files"])
