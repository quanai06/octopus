from pathlib import Path

OCTOPUS_DIR = Path(".octopus")
CONFIG_FILE = OCTOPUS_DIR / "config.yaml"
STATE_FILE = OCTOPUS_DIR / "project_state.json"
CONTEXT_DIR = OCTOPUS_DIR / "context"
CURRENT_CONTEXT = CONTEXT_DIR / "current_context.md"
EXPERIMENTS_DIR = OCTOPUS_DIR / "experiments"
ADR_DIR = OCTOPUS_DIR / "adr"

REQUIREMENTS_MD = Path("requirements.md")
ML_DESIGN_MD = Path("ml_design.md")
EXPERIMENT_MD = Path("experiment_plan.md")
TASKS_MD = Path("tasks.md")
CLAUDE_MD = Path("CLAUDE.md")
AGENTS_MD = Path("AGENTS.md")
