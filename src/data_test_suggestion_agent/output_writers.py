"""JSON artifact writers for the Data Test Suggestion Agent CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRACE_FILE_NAME = "data_test_trace.json"
PROFILE_FILE_NAME = "dataset_profile.json"
PAYLOAD_FILE_NAME = "test_suggestion_payload.json"
VALIDATED_SUGGESTIONS_FILE_NAME = "validated_test_suggestions.json"
REJECTED_SUGGESTIONS_FILE_NAME = "rejected_test_suggestions.json"
TEST_EXECUTION_RESULTS_FILE_NAME = "test_execution_results.json"


def write_json_artifact(output_dir: Path, file_name: str, payload: dict[str, Any]) -> Path:
    """Write a deterministic JSON artifact and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / file_name
    artifact_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact_path
