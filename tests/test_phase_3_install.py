import json

from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.install.hooks import baseline_guard
from octopus.install.installer import install, uninstall
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


# --- installer engine ------------------------------------------------------


def test_install_writes_claude_commands_and_hook(tmp_path):
    results = install(["claude"], home=tmp_path)

    commands = tmp_path / ".claude" / "commands"
    assert (commands / "octopus-baseline.md").exists()
    assert (commands / "octopus-train.md").exists()
    assert (commands / "octopus-tune.md").exists()
    baseline = (commands / "octopus-baseline.md").read_text(encoding="utf-8")
    assert "octopus init --runtime claude,codex" in baseline
    assert "octopus context --task" in baseline
    content = (commands / "octopus-train.md").read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "baseline-first" in content.lower()

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands_hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "octopus.install.hooks baseline-guard" in commands_hook
    assert results[0].hook_added is True


def test_install_writes_codex_prompts_and_skills(tmp_path):
    install(["codex"], home=tmp_path)
    prompts = tmp_path / ".codex" / "prompts"
    assert (prompts / "octopus-baseline.md").exists()
    assert (prompts / "octopus-plan.md").exists()
    assert "One-shot Octopus setup" in (prompts / "octopus-baseline.md").read_text(
        encoding="utf-8"
    )
    # Codex prompts are plain markdown (no Claude frontmatter block).
    assert not (prompts / "octopus-plan.md").read_text(encoding="utf-8").startswith("---")

    skill = tmp_path / ".codex" / "skills" / "octopus-baseline"
    assert (skill / "SKILL.md").exists()
    assert (skill / "agents" / "openai.yaml").exists()
    skill_body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert "name: octopus-baseline" in skill_body
    assert "octopus context --task" in skill_body
    assert "Octopus Baseline" in (skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )


def test_install_is_idempotent_for_hook(tmp_path):
    install(["claude"], home=tmp_path)
    second = install(["claude"], home=tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    # Hook must not be duplicated on reinstall.
    pre = settings["hooks"]["PreToolUse"]
    commands = [h["command"] for entry in pre for h in entry["hooks"]]
    assert commands.count("python -m octopus.install.hooks baseline-guard") == 1
    assert second[0].hook_added is False


def test_install_preserves_existing_settings(tmp_path):
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

    install(["claude"], home=tmp_path)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert "hooks" in settings


def test_uninstall_removes_files_and_hook(tmp_path):
    install(["claude", "codex"], home=tmp_path)
    uninstall(["claude", "codex"], home=tmp_path)

    assert not (tmp_path / ".claude" / "commands" / "octopus-train.md").exists()
    assert not (tmp_path / ".claude" / "commands" / "octopus-baseline.md").exists()
    assert not (tmp_path / ".codex" / "prompts" / "octopus-plan.md").exists()
    assert not (tmp_path / ".codex" / "prompts" / "octopus-baseline.md").exists()
    assert not (tmp_path / ".codex" / "skills" / "octopus-baseline" / "SKILL.md").exists()
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "PreToolUse" not in settings.get("hooks", {})


# --- baseline-guard hook ---------------------------------------------------


def _train_payload() -> str:
    return json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "python train.py --epochs 3"}}
    )


def test_baseline_guard_blocks_training_without_baseline(tmp_project):
    runner.invoke(app, ["init", "--force"])
    write_state(sample_ml_state())  # ML project, gate active, no baseline yet

    assert baseline_guard(_train_payload()) == 2


def test_baseline_guard_allows_after_baseline(tmp_project):
    runner.invoke(app, ["init", "--force"])
    write_state(sample_ml_state())
    runner.invoke(app, ["exp", "log", "--kind", "baseline", "--name", "b", "--metric=macro_f1=0.5"])

    assert baseline_guard(_train_payload()) == 0


def test_baseline_guard_ignores_non_training_commands(tmp_project):
    runner.invoke(app, ["init", "--force"])
    write_state(sample_ml_state())
    payload = json.dumps({"tool_input": {"command": "ls -la"}})
    assert baseline_guard(payload) == 0


def test_baseline_guard_ignores_when_no_project(tmp_project):
    # No .octopus state -> hook must not block.
    assert baseline_guard(_train_payload()) == 0


def _cmd(command: str) -> str:
    return json.dumps({"tool_input": {"command": command}})


def test_baseline_guard_blocks_custom_script_names(tmp_project):
    # Regression for the regex gap found in the Claude Code eval run:
    # custom training/fine-tune script names must also be blocked pre-baseline.
    runner.invoke(app, ["init", "--force"])
    write_state(sample_ml_state())
    for command in (
        "python train_phobert.py --model vinai/phobert-base",
        "python train-model.py",
        "python src/train.py",
        "python finetune_phobert.py",
        "python fine_tune.py",
        "accelerate launch train.py",
        "torchrun train.py",
        "deepspeed train.py",
    ):
        assert baseline_guard(_cmd(command)) == 2, f"should block: {command}"


def test_baseline_guard_allows_non_training_lookalikes(tmp_project):
    runner.invoke(app, ["init", "--force"])
    write_state(sample_ml_state())
    for command in (
        "python baseline_skeleton.py",
        "python preprocess.py",
        "python evaluate.py",
        "python tests/datasets/inspect.py",
    ):
        assert baseline_guard(_cmd(command)) == 0, f"should allow: {command}"


# --- CLI surface -----------------------------------------------------------


def test_install_cli_command(tmp_path):
    result = runner.invoke(app, ["install", "--runtime", "claude", "--home", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".claude" / "commands" / "octopus-status.md").exists()
    assert "/octopus-status" in result.output


def test_install_cli_codex_message_uses_prompt_name(tmp_path):
    result = runner.invoke(app, ["install", "--runtime", "codex", "--home", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".codex" / "prompts" / "octopus-status.md").exists()
    assert (tmp_path / ".codex" / "skills" / "octopus-baseline" / "SKILL.md").exists()
    last_line = result.output.strip().splitlines()[-1]
    assert "@octopus-baseline" in last_line
    assert "/octopus-status" not in last_line


def test_install_cli_rejects_unknown_runtime(tmp_path):
    result = runner.invoke(app, ["install", "--runtime", "vim", "--home", str(tmp_path)])
    assert result.exit_code == 1
