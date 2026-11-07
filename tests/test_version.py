import tomllib
from pathlib import Path

import agentic_larp

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    with PYPROJECT.open("rb") as manifest:
        expected = tomllib.load(manifest)["project"]["version"]
    assert agentic_larp.__version__ == expected
