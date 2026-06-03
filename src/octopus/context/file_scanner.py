from pathlib import Path

import pathspec

DEFAULT_EXCLUDED_PATTERNS = [
    ".venv/",
    "__pycache__/",
    ".git/",
    "node_modules/",
    "dist/",
    "build/",
    "*.pt",
    "*.pth",
    "*.ckpt",
    "*.onnx",
    "*.pkl",
    "*.joblib",
    "*.csv",
    "*.xlsx",
    "*.parquet",
    "*.jsonl",
    "*.log",
    "wandb/",
    "mlruns/",
    "checkpoints/",
    "data/",
    "datasets/",
]


def load_exclude_spec(root: Path = Path(".")) -> tuple[pathspec.PathSpec, list[str]]:
    patterns = list(DEFAULT_EXCLUDED_PATTERNS)
    gitignore = root / ".gitignore"
    if gitignore.exists():
        patterns.extend(
            line.strip()
            for line in gitignore.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    return pathspec.PathSpec.from_lines("gitignore", patterns), patterns


def scan_project_files(root: Path = Path(".")) -> tuple[list[str], list[str], list[str]]:
    spec, patterns = load_exclude_spec(root)
    included: list[str] = []
    excluded: list[str] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if spec.match_file(rel):
            excluded.append(rel)
        else:
            included.append(rel)
    return sorted(included), sorted(excluded), patterns
