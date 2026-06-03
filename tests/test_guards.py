from pathlib import Path

import pytest

from octopus.core.guards import require_init, require_ml_project, require_state
from tests.helpers import sample_ml_state, write_state


def test_require_init_fails_without_octopus_dir(tmp_project):
    with pytest.raises(SystemExit) as exc:
        require_init()

    assert exc.value.code == 1


def test_require_state_fails_without_state_file(tmp_project):
    Path(".octopus").mkdir()

    with pytest.raises(SystemExit) as exc:
        require_state()

    assert exc.value.code == 1


def test_require_ml_project_fails_for_software(tmp_project):
    write_state(sample_ml_state(project_type="software", task_type=None))

    with pytest.raises(SystemExit) as exc:
        require_ml_project()

    assert exc.value.code == 0
