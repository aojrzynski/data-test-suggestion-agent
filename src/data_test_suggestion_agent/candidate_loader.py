"""Load manually supplied local candidate test suggestion JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CandidateLoadError(ValueError):
    """Expected user-facing candidate loading or shape validation failure."""


def load_candidate_tests(candidates_path: str) -> list[dict[str, Any]]:
    """Load and validate the outer JSON shape for candidate suggestions.

    The loader only confirms that the file is local JSON with a top-level
    ``candidate_tests`` array of objects. Detailed candidate schema, safety, and
    dataset-aware checks are performed by the deterministic validator.
    """
    path = Path(candidates_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CandidateLoadError(f"Candidate file not found: {candidates_path}") from exc
    except OSError as exc:
        raise CandidateLoadError(f"Could not read candidate file: {exc}") from exc

    try:
        loaded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CandidateLoadError(f"Malformed candidate JSON: {exc}") from exc

    if not isinstance(loaded, dict):
        raise CandidateLoadError("Candidate JSON top level must be an object.")
    if "candidate_tests" not in loaded:
        raise CandidateLoadError("Candidate JSON must include 'candidate_tests'.")
    candidate_tests = loaded["candidate_tests"]
    if not isinstance(candidate_tests, list):
        raise CandidateLoadError("Candidate JSON field 'candidate_tests' must be a list.")
    for index, candidate in enumerate(candidate_tests):
        if not isinstance(candidate, dict):
            raise CandidateLoadError(
                f"Candidate entry at index {index} must be an object."
            )
    return list(candidate_tests)
