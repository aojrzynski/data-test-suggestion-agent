"""Tests for local candidate JSON loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_test_suggestion_agent.candidate_loader import CandidateLoadError, load_candidate_tests

VALID_FIXTURE = Path("config/examples/customer_candidate_tests.json")


def test_loads_valid_candidate_json():
    """The loader should return candidate objects from valid JSON."""
    candidates = load_candidate_tests(str(VALID_FIXTURE))

    assert len(candidates) >= 3
    assert candidates[0]["test_id"] == "customer_id_not_null"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{bad json", "Malformed candidate JSON"),
        (json.dumps([{"candidate_tests": []}]), "top level must be an object"),
        (json.dumps({}), "must include 'candidate_tests'"),
        (json.dumps({"candidate_tests": {}}), "must be a list"),
        (json.dumps({"candidate_tests": ["not an object"]}), "index 0 must be an object"),
    ],
)
def test_rejects_invalid_candidate_json_shapes(tmp_path, content, message):
    """Malformed or incorrectly shaped candidate JSON should fail cleanly."""
    path = tmp_path / "candidates.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(CandidateLoadError, match=message):
        load_candidate_tests(str(path))


def test_handles_missing_candidate_file_cleanly(tmp_path):
    """A missing file should raise a user-facing loader error."""
    with pytest.raises(CandidateLoadError, match="Candidate file not found"):
        load_candidate_tests(str(tmp_path / "missing.json"))
