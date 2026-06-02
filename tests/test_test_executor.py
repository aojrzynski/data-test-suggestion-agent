"""Tests for deterministic local candidate execution."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd

from data_test_suggestion_agent.candidate_models import CandidateTestSuggestion, ValidatedCandidate
from data_test_suggestion_agent.test_executor import (
    build_test_execution_results_artifact,
    execute_validated_candidates,
)


def _candidate(test_id: str, test_type: str, column: str, parameters: dict | None = None) -> ValidatedCandidate:
    return ValidatedCandidate(
        candidate=CandidateTestSuggestion(
            test_id=test_id,
            test_type=test_type,
            column=column,
            severity="high",
            parameters=parameters or {},
            rationale="test fixture",
            suggested_by="manual_fixture",
        ),
        validation_notes=["fixture_validated"],
    )


def _result_by_id(results):
    return {result.test_id: result.to_dict() for result in results}


def test_executor_runs_supported_types_with_aggregate_metrics_only():
    """Supported executors should return counts without raw failing values."""
    dataframe = pd.DataFrame(
        {
            "id": ["A", "B", "B", None],
            "status": ["active", "paused", "bad", None],
            "age": [10, -1, 121, None],
            "date_text": ["2024-01-01", "not-a-date", None, "2024-02-01"],
            "event_date": ["2024-01-01", "not-a-date", "2027-01-01", None],
            "code": ["ABC-12", "ABC-123", None, "XYZ-99"],
            "email": ["alex.rivera@example.com", "blair.chen@example.com", "x", None],
        }
    )
    candidates = [
        _candidate("id_not_null", "not_null", "id"),
        _candidate("id_unique", "unique", "id"),
        _candidate("status_allowed", "accepted_values", "status", {"allowed_values": ["active", "paused"]}),
        _candidate("age_range", "numeric_range", "age", {"min": 0, "max": 120}),
        _candidate("date_parse", "date_parseable", "date_text"),
        _candidate("event_not_future", "date_not_future", "event_date"),
        _candidate("code_regex", "regex_match", "code", {"pattern": r"[A-Z]{3}-\d{2}"}),
        _candidate("email_not_null", "not_null", "email"),
    ]

    results = execute_validated_candidates(
        dataframe=dataframe,
        validated_candidates=candidates,
        reference_date=date(2026, 1, 1),
    )
    by_id = _result_by_id(results)

    assert by_id["id_not_null"]["status"] == "failed"
    assert by_id["id_not_null"]["evaluated_row_count"] == 4
    assert by_id["id_not_null"]["failure_count"] == 1
    assert by_id["id_not_null"]["metrics"] == {"null_count": 1}

    assert by_id["id_unique"]["failure_count"] == 2
    assert by_id["id_unique"]["metrics"] == {"duplicate_value_count": 1}

    assert by_id["status_allowed"]["failure_count"] == 1
    assert by_id["status_allowed"]["metrics"] == {"allowed_value_count": 2, "nulls_ignored": True}

    assert by_id["age_range"]["failure_count"] == 2
    assert by_id["age_range"]["metrics"] == {"max_bound": 120, "min_bound": 0, "nulls_ignored": True}

    assert by_id["date_parse"]["failure_count"] == 1
    assert by_id["date_parse"]["metrics"] == {"nulls_ignored": True}

    assert by_id["event_not_future"]["failure_count"] == 2
    assert by_id["event_not_future"]["metrics"] == {
        "future_date_count": 1,
        "nulls_ignored": True,
        "parse_failure_count": 1,
        "reference_date": "2026-01-01",
    }

    assert by_id["code_regex"]["failure_count"] == 1
    assert by_id["code_regex"]["metrics"] == {"nulls_ignored": True, "pattern_length": 14}
    assert by_id["email_not_null"]["status"] == "failed"

    artifact_text = json.dumps(build_test_execution_results_artifact(validated_candidate_count=len(candidates), execution_results=results))
    for forbidden in [
        "alex.rivera@example.com",
        "blair.chen@example.com",
        "not-a-date",
        "ABC-123",
        "bad",
        "duplicate_values",
        "unexpected_values",
        "failing_values",
        "raw_rows_included\": true",
        "example_values_included\": true",
        "approved_tests\": true",
        "status\": " + json.dumps("approved"),
    ]:
        assert forbidden not in artifact_text


def test_executor_returns_passed_and_does_not_execute_rejected_candidates():
    """The executor API only receives validated candidates and summarizes them."""
    dataframe = pd.DataFrame({"id": ["A", "B"], "status": ["active", "paused"]})
    results = execute_validated_candidates(
        dataframe=dataframe,
        validated_candidates=[
            _candidate("id_not_null", "not_null", "id"),
            _candidate("status_allowed", "accepted_values", "status", {"allowed_values": ["active", "paused"]}),
        ],
    )
    artifact = build_test_execution_results_artifact(validated_candidate_count=2, execution_results=results)

    assert [result.status for result in results] == ["passed", "passed"]
    assert artifact["summary"] == {
        "validated_candidate_count": 2,
        "executed_count": 2,
        "passed_count": 2,
        "failed_count": 0,
    }
    assert artifact["candidate_tests_generated_by_this_agent"] is False
    assert artifact["llm_called"] is False
    assert artifact["validated_candidates_are_approved_tests"] is False
    assert artifact["tests_executed"] is True
    assert artifact["execution_is_local_only"] is True
    assert "rejected_candidates" not in artifact
