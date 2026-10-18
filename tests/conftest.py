"""Shared fixtures: JSON shaped like real Figma REST API responses."""

import copy
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def file_response() -> dict:
    return load_fixture("file_response.json")


@pytest.fixture
def variables_response() -> dict:
    return load_fixture("variables_local.json")


@pytest.fixture
def nodes_response() -> dict:
    return load_fixture("nodes_response.json")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def clone():
    """Deep-copy helper so a test can mutate fixture data safely."""
    return copy.deepcopy
