from pathlib import Path

from typer.testing import CliRunner

from octopus.cli.commands.ask import (
    CUSTOM_CHOICE,
    _checkbox,
    _checkbox_or_text,
    _select_or_text,
    baseline_choices_for_task,
)
from octopus.cli.main import app
from tests.helpers import write_state


def test_help_lists_phase_1_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in [
        "init",
        "ask",
        "plan",
        "ml-plan",
        "tasks",
        "baseline-spec",
        "context",
        "sync",
        "status",
        "exp",
        "task",
    ]:
        assert command in result.output


def test_status_formats_context_timestamp(tmp_project):
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    write_state()
    context = Path(".octopus/context/current_context.md")
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text("> Estimated tokens: 123\n", encoding="utf-8")

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Last built:" in result.output
    assert ".000000" not in result.output


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


def test_baseline_choices_are_task_specific():
    assert baseline_choices_for_task("text_classification") == [
        "TF-IDF + Logistic Regression",
        "TF-IDF + LinearSVC",
    ]
    assert baseline_choices_for_task("retrieval")[0] == "BM25"


def test_select_or_text_accepts_custom_value():
    class FakePrompt:
        def __init__(self, value):
            self.value = value

        def ask(self):
            return self.value

    class FakeQuestionary:
        @staticmethod
        def select(message, choices, default=None):
            assert CUSTOM_CHOICE in choices
            return FakePrompt(CUSTOM_CHOICE)

        @staticmethod
        def text(message, default=""):
            return FakePrompt("CatBoost baseline")

    answer = _select_or_text(
        FakeQuestionary,
        "Baseline model?",
        ["Linear Regression", "Random Forest"],
        custom_message="Custom baseline model?",
    )

    assert answer == "CatBoost baseline"


def test_checkbox_or_text_accepts_custom_runtime():
    class FakeChoice:
        def __init__(self, title, value, checked):
            self.title = title
            self.value = value
            self.checked = checked

    class FakePrompt:
        def __init__(self, value):
            self.value = value

        def ask(self):
            return self.value

    class FakeQuestionary:
        Choice = FakeChoice

        @staticmethod
        def checkbox(message, choices):
            assert any(choice.value == CUSTOM_CHOICE for choice in choices)
            return FakePrompt(["codex", CUSTOM_CHOICE])

        @staticmethod
        def text(message, default=""):
            return FakePrompt("cursor")

    answer = _checkbox_or_text(
        FakeQuestionary,
        "Runtime?",
        ["claude", "codex", "none"],
        ["codex"],
        custom_message="Custom runtime?",
    )

    assert answer == ["codex", "cursor"]
