from pathlib import Path

OCTOPUS_DIR = Path(".octopus")
CONFIG_FILE = OCTOPUS_DIR / "config.yaml"
STATE_FILE = OCTOPUS_DIR / "project_state.json"
TASK_STATE_FILE = OCTOPUS_DIR / "tasks.json"
CONTEXT_DIR = OCTOPUS_DIR / "context"
CURRENT_CONTEXT = CONTEXT_DIR / "current_context.md"
EXPERIMENTS_DIR = OCTOPUS_DIR / "experiments"
EXPERIMENT_INDEX = EXPERIMENTS_DIR / "index.yaml"
REPORTS_DIR = OCTOPUS_DIR / "reports"
EXPERIMENT_REPORT_MD = REPORTS_DIR / "experiment_report.md"
ADR_DIR = OCTOPUS_DIR / "adr"

REQUIREMENTS_MD = Path("requirements.md")
ML_DESIGN_MD = Path("ml_design.md")
EXPERIMENT_MD = Path("experiment_plan.md")
DATA_STRATEGY_MD = Path("data_strategy.md")
COMPUTE_BUDGET_MD = Path("compute_budget.md")
TASKS_MD = Path("tasks.md")
CLAUDE_MD = Path("CLAUDE.md")
AGENTS_MD = Path("AGENTS.md")
