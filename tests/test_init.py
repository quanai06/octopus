from pathlib import Path

from typer.testing import CliRunner

from octopus.cli.main import app

runner = CliRunner()


def test_init_creates_all_files(tmp_project):
    result = runner.invoke(app, ["init", "--force"])

    assert result.exit_code == 0
    assert Path(".octopus/config.yaml").exists()
    assert Path(".octopus/project_state.json").exists()
    assert Path("requirements.md").exists()
    assert Path("ml_design.md").exists()
    assert Path("experiment_plan.md").exists()
    assert Path("tasks.md").exists()


def test_init_creates_claude_md_when_runtime_claude(tmp_project):
    runner.invoke(app, ["init", "--runtime", "claude", "--force"])

    assert Path("CLAUDE.md").exists()
    assert not Path("AGENTS.md").exists()


def test_init_creates_agents_md_when_runtime_codex(tmp_project):
    runner.invoke(app, ["init", "--runtime", "codex", "--force"])

    assert Path("AGENTS.md").exists()
    assert not Path("CLAUDE.md").exists()


def test_init_does_not_overwrite_without_confirm(tmp_project, monkeypatch):
    Path(".octopus").mkdir()
    marker = Path("requirements.md")
    marker.write_text("keep me", encoding="utf-8")

    class DeniedConfirm:
        def ask(self):
            return False

    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: DeniedConfirm())
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert marker.read_text(encoding="utf-8") == "keep me"


def test_init_creates_octopus_subdirs(tmp_project):
    runner.invoke(app, ["init", "--force"])

    assert Path(".octopus/context").is_dir()
    assert Path(".octopus/experiments").is_dir()
    assert Path(".octopus/adr").is_dir()
