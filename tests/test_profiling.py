"""Tests for safe aggregate profiling."""

from __future__ import annotations

import json

import pandas as pd

from data_test_suggestion_agent.models import DatasetMetadata
from data_test_suggestion_agent.profiling import profile_dataset


def _metadata(frame: pd.DataFrame) -> DatasetMetadata:
    return DatasetMetadata(
        input_path="sample.csv",
        file_name="sample.csv",
        file_extension=".csv",
        sheet_name=None,
        row_count=len(frame),
        column_count=len(frame.columns),
        columns=list(frame.columns),
    )


def test_profile_includes_safe_aggregate_column_evidence():
    """Profiling should compute counts, ratios, and bounded stats only."""
    frame = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3", "C4"],
            "email": ["ada@example.com", "bea@example.com", "cal@example.com", "dee@example.com"],
            "age": [20, 30, None, 40],
            "status": ["active", "active", "paused", ""],
            "signup_date": ["2024-01-01", "2024-01-02", None, "2024-01-04"],
        }
    )

    profile = profile_dataset(frame, _metadata(frame)).to_dict()
    columns = {column["name"]: column for column in profile["columns"]}

    assert profile["row_count"] == 4
    assert profile["column_count"] == 5
    assert columns["customer_id"]["likely_identifier_candidate"] is True
    assert columns["customer_id"]["unique_count"] == 4
    assert columns["age"]["profile_type"] == "numeric"
    assert columns["age"]["null_count"] == 1
    assert columns["age"]["unique_count"] == 3
    assert columns["age"]["numeric_min"] == 20.0
    assert columns["age"]["numeric_max"] == 40.0
    assert columns["age"]["numeric_mean"] == 30.0
    assert columns["status"]["profile_type"] == "text"
    assert columns["status"]["min_length"] == 0
    assert columns["status"]["max_length"] == 6
    assert columns["status"]["empty_string_count"] == 1
    assert columns["status"]["low_cardinality_candidate"] is False
    assert columns["signup_date"]["profile_type"] == "datetime"
    assert columns["signup_date"]["parseable_date_count"] == 3
    assert columns["signup_date"]["parseable_date_ratio"] == 1.0
    assert columns["signup_date"]["min_date"] == "2024-01-01"
    assert columns["signup_date"]["max_date"] == "2024-01-04"


def test_profile_does_not_include_raw_rows_or_example_values():
    """Profile JSON should not leak raw sample values such as emails."""
    frame = pd.DataFrame(
        {
            "email": ["alex.rivera@example.com", "blair.chen@example.com"],
            "status": ["active", "paused"],
        }
    )

    profile_json = json.dumps(profile_dataset(frame, _metadata(frame)).to_dict())

    assert "alex.rivera@example.com" not in profile_json
    assert "blair.chen@example.com" not in profile_json
    assert "example_values" not in profile_json
    assert "top_values" not in profile_json
    assert "raw_rows" not in profile_json
