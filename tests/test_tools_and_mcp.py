import json
from pathlib import Path

from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.mcp_server import handle_message
from octopus.tools.registry import call_tool, list_tool_specs
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _init_project_with_tasks() -> None:
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    write_state(sample_ml_state())
    assert runner.invoke(app, ["tasks", "--force"]).exit_code == 0


def _write_minimal_plan_files() -> None:
    for name in [
        "requirements.md",
        "ml_design.md",
        "data_strategy.md",
        "experiment_plan.md",
        "compute_budget.md",
        "tasks.md",
    ]:
        Path(name).write_text(f"# {name}\n\nBaseline first.\n", encoding="utf-8")


def _task_status(task_id: str) -> str:
    data = json.loads(Path(".octopus/tasks.json").read_text(encoding="utf-8"))
    return next(task["status"] for task in data["tasks"] if task["id"] == task_id)


def test_function_call_specs_expose_json_schemas():
    specs = {spec.name: spec for spec in list_tool_specs()}

    assert "octopus_build_context" in specs
    assert specs["octopus_build_context"].input_schema["type"] == "object"
    assert "result" in specs["octopus_build_context"].output_schema["properties"]
    assert "octopus_ingest_run" in specs
    assert "octopus_profile_baseline" in specs


def test_tool_call_status_returns_structured_output(tmp_project):
    _init_project_with_tasks()

    result = call_tool("octopus_status")

    payload = result.model_dump(mode="json")
    assert payload["initialized"] is True
    assert payload["project"]["name"] == "Vietnamese Emotion Classifier"
    assert payload["next_task"]["id"] == "T001"


def test_cli_json_protocol_for_status_and_task_next(tmp_project):
    _init_project_with_tasks()

    status = runner.invoke(app, ["status", "--json"])
    task_next = runner.invoke(app, ["task", "next", "--json"])

    assert status.exit_code == 0
    status_payload = json.loads(status.output)
    assert status_payload["ok"] is True
    assert status_payload["tool"] == "octopus_status"
    assert status_payload["result"]["project"]["metric"] == "macro_f1"

    assert task_next.exit_code == 0
    task_payload = json.loads(task_next.output)
    assert task_payload["ok"] is True
    assert task_payload["result"]["task"]["id"] == "T001"


def test_context_json_builds_current_context(tmp_project):
    _init_project_with_tasks()
    _write_minimal_plan_files()

    result = runner.invoke(
        app,
        ["context", "--task", "train baseline", "--profile", "training", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["tool"] == "octopus_build_context"
    assert payload["result"]["result"]["output_path"] == ".octopus/context/current_context.md"
    assert Path(".octopus/context/current_context.md").exists()


def test_ingest_json_marks_baseline_tasks_done(tmp_project):
    _init_project_with_tasks()
    run_dir = Path("runs/baseline")
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text('{"macro_f1": 0.61}', encoding="utf-8")

    result = runner.invoke(
        app,
        ["exp", "ingest", "--run-dir", str(run_dir), "--kind", "baseline", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["tool"] == "octopus_ingest_run"
    assert payload["result"]["record"]["id"] == "E001"
    assert payload["result"]["baseline_tasks_marked_done"] is True
    assert _task_status("T012") == "done"


def test_mcp_lists_and_calls_tools(tmp_project):
    _init_project_with_tasks()

    listed = handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    called = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "octopus_status", "arguments": {}},
        }
    )

    assert listed is not None
    tools = listed["result"]["tools"]
    assert any(tool["name"] == "octopus_status" for tool in tools)

    assert called is not None
    assert called["result"]["structuredContent"]["initialized"] is True
    assert called["result"]["isError"] is False


def test_mcp_resources_read_current_context(tmp_project):
    _init_project_with_tasks()
    Path(".octopus/context").mkdir(parents=True, exist_ok=True)
    Path(".octopus/context/current_context.md").write_text("# Current\n", encoding="utf-8")

    listed = handle_message({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
    read = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/read",
            "params": {"uri": "octopus://context/current"},
        }
    )

    assert listed is not None
    assert any(
        resource["uri"] == "octopus://context/current"
        for resource in listed["result"]["resources"]
    )
    assert read is not None
    assert read["result"]["contents"][0]["text"] == "# Current\n"
