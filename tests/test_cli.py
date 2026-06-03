from typer.testing import CliRunner

from octopus.cli.commands.ask import _checkbox
from octopus.cli.main import app


def test_help_lists_phase_1_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["init", "ask", "plan", "ml-plan", "tasks", "context", "sync", "status"]:
        assert command in result.output


def test_checkbox_accepts_existing_runtime_default():
    captured = {}

    class FakeChoice:
        def __init__(self, title, value, checked):
            self.title = title
            self.value = value
            self.checked = checked

    class FakePrompt:
        def ask(self):
            return ["codex"]

    class FakeQuestionary:
        Choice = FakeChoice

        @staticmethod
        def checkbox(message, choices):
            captured["message"] = message
            captured["choices"] = choices
            return FakePrompt()

    answer = _checkbox(
        FakeQuestionary,
        "Runtime?",
        ["claude", "codex", "none"],
        ["codex"],
    )

    assert answer == ["codex"]
    assert [choice.checked for choice in captured["choices"]] == [False, True, False]
