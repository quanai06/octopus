"""Source content for the artifacts Octopus installs into AI runtimes.

These are thin *routers*: short markdown files that point the host runtime
(Claude Code / Codex) at the deterministic Octopus CLI and its file-state, so
the model is steered into the baseline-first workflow with a small token surface.
The CLI remains the brain; the runtime runs the LLM loop (GSD-style).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandRouter:
    name: str
    description: str
    body: str
    allowed_tools: str = "Bash(octopus *), Read, Grep, Glob"


COMMAND_ROUTERS: tuple[CommandRouter, ...] = (
    CommandRouter(
        name="octopus-plan",
        description="Plan an ML/DL/RAG project with Octopus (intake -> plan -> tasks).",
        body=(
            "Use the Octopus CLI to set up a baseline-first plan.\n\n"
            "1. Run `octopus ask` to capture requirements, or confirm an existing "
            "`requirements.md`.\n"
            "2. Run `octopus plan`, then `octopus ml-plan`, then `octopus tasks`.\n"
            "3. Run `octopus task next` to find the first unblocked task.\n"
            "4. Read `.octopus/context/current_context.md` before writing any code.\n\n"
            "Do not start main-model work before a baseline exists."
        ),
    ),
    CommandRouter(
        name="octopus-train",
        description="Run the Octopus baseline-first training loop.",
        body=(
            "Follow the Octopus baseline-first loop. Never train a main model before a "
            "baseline.\n\n"
            "1. Run `octopus task next` and "
            "`octopus context --task \"<task>\" --profile training`.\n"
            "2. Read `.octopus/context/current_context.md` and "
            "`.octopus/plans/selected_direction.yaml` if present.\n"
            "3. Implement only the selected direction. One controlled change per run.\n"
            "4. After a run, ingest it: `octopus exp ingest --run-dir <run_dir>` "
            "(auto-detects MLflow / W&B / TensorBoard).\n"
            "5. Then run `octopus exp profile` to understand the baseline before tuning.\n\n"
            "Never tune on the test set or change the train/validation/test split unless the "
            "selected direction says so."
        ),
    ),
    CommandRouter(
        name="octopus-tune",
        description="Pick and implement the next tuning direction from the baseline profile.",
        body=(
            "Improve on the current baseline with one disciplined change.\n\n"
            "1. Run `octopus exp profile` and read `.octopus/reports/baseline_profile.md`.\n"
            "2. Run `octopus exp next` and read `.octopus/plans/next_steps.md`.\n"
            "3. Choose a direction: `octopus exp choose D<n>`, then "
            "`octopus context --direction D<n>`.\n"
            "4. Implement ONLY the top-ranked technique for that direction. Respect the "
            "\"Do Not Try Yet\" list.\n"
            "5. Ingest and re-profile after the run."
        ),
    ),
    CommandRouter(
        name="octopus-status",
        description="Show the Octopus project snapshot and the next action.",
        body=(
            "1. Run `octopus status`.\n"
            "2. Run `octopus task next`.\n"
            "3. Summarize the current best experiment, the target gap, and the recommended "
            "next direction."
        ),
    ),
    CommandRouter(
        name="octopus-resume",
        description="Restore Octopus working context after a session/context reset.",
        body=(
            "Restore where you left off.\n\n"
            "1. Run `octopus resume` and read its output.\n"
            "2. Read `.octopus/session/current.md` (active session state).\n"
            "3. Read `.octopus/context/current_context.md` and "
            "`.octopus/plans/selected_direction.yaml` if present.\n"
            "4. Read `.octopus/memory/experiments.md` to avoid repeating failed directions.\n"
            "5. Continue ONLY the in-progress task/direction. Do not start new work."
        ),
    ),
)


@dataclass(frozen=True)
class AgentDef:
    name: str
    description: str
    body: str
    tools: str = "Read, Grep, Glob, Bash"
    model: str = "inherit"
    color: str = "cyan"
    extra_frontmatter: dict[str, str] = field(default_factory=dict)


_AGENT_GUARDRAILS = (
    "\n\n## Octopus rules\n"
    "- Use the `octopus` CLI; treat `.octopus/` files as the source of truth.\n"
    "- Never train or log a main model before a completed baseline exists.\n"
    "- Do not change the train/validation/test split unless the selected direction says so.\n"
    "- Do not tune on the test set. Make one controlled change per run.\n"
    "- Record progress with `octopus session log` so work survives a context reset."
)

AGENT_DEFS: tuple[AgentDef, ...] = (
    AgentDef(
        name="octopus-baseline-runner",
        description=(
            "Establish and log the first reproducible baseline. Use before any main-model work."
        ),
        tools="Read, Grep, Glob, Bash, Edit",
        body=(
            "You build the baseline-first comparison point for an ML/DL/RAG project.\n\n"
            "1. Read `requirements.md`, `ml_design.md`, and "
            "`.octopus/context/current_context.md`.\n"
            "2. Implement the simplest reproducible baseline from `experiment_plan.md`.\n"
            "3. Train it, then ingest the run: `octopus exp ingest --run-dir <run_dir> "
            "--kind baseline` (auto-detects MLflow/W&B/TensorBoard).\n"
            "4. Confirm the baseline is logged and the main-model task is unblocked."
            + _AGENT_GUARDRAILS
        ),
    ),
    AgentDef(
        name="octopus-experiment-analyst",
        description="Analyze and profile a finished run; diagnose bottlenecks before tuning.",
        tools="Read, Grep, Glob, Bash",
        body=(
            "You turn a finished run into a diagnosis.\n\n"
            "1. Run `octopus exp analyze <id>` and `octopus exp profile`.\n"
            "2. Read `.octopus/reports/baseline_profile.md` and the training review.\n"
            "3. Report bias/variance, weak classes, data-quality risks, and headroom vs target.\n"
            "4. Hand off the top-ranked technique to the tuner; do not edit training code yourself."
            + _AGENT_GUARDRAILS
        ),
    ),
    AgentDef(
        name="octopus-tuner",
        description="Implement exactly one selected tuning direction on top of the baseline.",
        tools="Read, Grep, Glob, Bash, Edit",
        body=(
            "You implement one disciplined improvement.\n\n"
            "1. Run `octopus exp next`; read `.octopus/plans/next_steps.md`.\n"
            "2. `octopus exp choose D<n>`, then `octopus context --direction D<n>`.\n"
            "3. Implement ONLY the top-ranked technique for that direction. Respect "
            "\"Do Not Try Yet\".\n"
            "4. Re-run, ingest, and re-profile to measure the change." + _AGENT_GUARDRAILS
        ),
    ),
    AgentDef(
        name="octopus-data-auditor",
        description="Audit dataset splits, leakage, duplicates, and class imbalance.",
        tools="Read, Grep, Glob, Bash",
        body=(
            "You protect the evaluation from being fooled.\n\n"
            "1. Read `data_strategy.md` and the dataset/split code.\n"
            "2. Check for train/val/test leakage, duplicate or near-duplicate samples, and "
            "label/support imbalance.\n"
            "3. Report concrete risks and the exact files/lines involved.\n"
            "4. Do not change the split; recommend fixes for the user to approve."
            + _AGENT_GUARDRAILS
        ),
    ),
    AgentDef(
        name="octopus-rag-evaluator",
        description=(
            "Build retrieval evaluation and check recall/citation before generation tuning."
        ),
        tools="Read, Grep, Glob, Bash",
        body=(
            "You make RAG quality measurable before prompt/generation changes.\n\n"
            "1. Build or read a fixed retrieval evaluation set.\n"
            "2. Measure Recall@k / source-hit; inspect failing queries.\n"
            "3. Verify every generated answer cites a retrieved source chunk (faithfulness).\n"
            "4. Recommend retrieval fixes (chunking, hybrid, reranker) only from the evidence."
            + _AGENT_GUARDRAILS
        ),
    ),
)


def render_command_router(router: CommandRouter) -> str:
    lines = [
        "---",
        f"description: {router.description}",
        f"allowed-tools: {router.allowed_tools}",
        "---",
        "",
        f"# {router.name}",
        "",
        router.body,
        "",
    ]
    return "\n".join(lines)


def render_codex_prompt(router: CommandRouter) -> str:
    # Codex prompt files are plain markdown; keep a description line, drop Claude-only keys.
    return f"# {router.name}\n\n> {router.description}\n\n{router.body}\n"


def render_agent_def(agent: AgentDef) -> str:
    lines = [
        "---",
        f"name: {agent.name}",
        f"description: {agent.description}",
        f"tools: {agent.tools}",
        f"model: {agent.model}",
        f"color: {agent.color}",
    ]
    for key, value in agent.extra_frontmatter.items():
        lines.append(f"{key}: {value}")
    lines.extend(["---", "", agent.body, ""])
    return "\n".join(lines)
