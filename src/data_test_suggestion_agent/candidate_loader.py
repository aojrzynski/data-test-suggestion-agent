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

    return parse_candidate_tests_json_text(raw_text, source_label="Candidate JSON")


def parse_candidate_tests_json_text(
    raw_text: str,
    *,
    source_label: str = "Candidate JSON",
    normalize_missing_parameters: bool = False,
) -> list[dict[str, Any]]:
    """Parse candidate JSON text and validate the shared outer shape.

    This helper is shared by manual file loading and LLM response parsing so
    both paths use the same top-level ``candidate_tests`` contract. Detailed
    candidate semantics remain the deterministic validator's responsibility.
    """
    try:
        loaded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CandidateLoadError(f"Malformed candidate JSON: {exc}") from exc

    if not isinstance(loaded, dict):
        raise CandidateLoadError(f"{source_label} top level must be an object.")
    if "candidate_tests" not in loaded:
        raise CandidateLoadError(f"{source_label} must include 'candidate_tests'.")
    candidate_tests = loaded["candidate_tests"]
    if not isinstance(candidate_tests, list):
        raise CandidateLoadError(f"{source_label} field 'candidate_tests' must be a list.")

    normalized: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidate_tests):
        if not isinstance(candidate, dict):
            raise CandidateLoadError(
                f"Candidate entry at index {index} must be an object."
            )
        candidate_copy = dict(candidate)
        if normalize_missing_parameters and "parameters" not in candidate_copy:
            candidate_copy["parameters"] = {}
        normalized.append(candidate_copy)
    return normalized
