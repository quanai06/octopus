import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path):
    original = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(original)
