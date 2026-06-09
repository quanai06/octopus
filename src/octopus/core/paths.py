from pathlib import Path

OCTOPUS_DIR = Path(".octopus")
CONFIG_FILE = OCTOPUS_DIR / "config.yaml"
STATE_FILE = OCTOPUS_DIR / "project_state.json"
TASK_STATE_FILE = OCTOPUS_DIR / "tasks.json"
CONTEXT_DIR = OCTOPUS_DIR / "context"
CURRENT_CONTEXT = CONTEXT_DIR / "current_context.md"
EXPERIMENTS_DIR = OCTOPUS_DIR / "experiments"
EXPERIMENT_INDEX = EXPERIMENTS_DIR / "index.yaml"
MEMORY_DIR = OCTOPUS_DIR / "memory"
EXPERIMENT_MEMORY_MD = MEMORY_DIR / "experiments.md"
BEST_RUNS_MD = MEMORY_DIR / "best_runs.md"
FAILURES_MD = MEMORY_DIR / "failures.md"
DECISIONS_MD = MEMORY_DIR / "decisions.md"
REPORTS_DIR = OCTOPUS_DIR / "reports"
EXPERIMENT_REPORT_MD = REPORTS_DIR / "experiment_report.md"
BASELINE_PROFILE_MD = REPORTS_DIR / "baseline_profile.md"
PLANS_DIR = OCTOPUS_DIR / "plans"
NEXT_STEPS_MD = PLANS_DIR / "next_steps.md"
NEXT_STEPS_YAML = PLANS_DIR / "next_steps.yaml"
SELECTED_DIRECTION_YAML = PLANS_DIR / "selected_direction.yaml"
ADR_DIR = OCTOPUS_DIR / "adr"
SESSION_DIR = OCTOPUS_DIR / "session"
SESSION_STATE = SESSION_DIR / "current.json"
SESSION_MD = SESSION_DIR / "current.md"

REQUIREMENTS_MD = Path("requirements.md")
ML_DESIGN_MD = Path("ml_design.md")
EXPERIMENT_MD = Path("experiment_plan.md")
DATA_STRATEGY_MD = Path("data_strategy.md")
COMPUTE_BUDGET_MD = Path("compute_budget.md")
TASKS_MD = Path("tasks.md")
BASELINE_SPEC_YAML = Path("baseline_spec.yaml")
CLAUDE_MD = Path("CLAUDE.md")
AGENTS_MD = Path("AGENTS.md")
