"""Tests for deterministic candidate suggestion validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_test_suggestion_agent.candidate_validator import validate_candidate_tests
from data_test_suggestion_agent.context_loader import load_context
from data_test_suggestion_agent.intake import load_dataset
from data_test_suggestion_agent.profiling import profile_dataset

SAMPLE_DATASET = Path("sample_data/customers/customers_for_test_suggestions.csv")
SAMPLE_CONTEXT = Path("config/examples/customer_dataset_context.yaml")


@pytest.fixture
def profile():
    """Return a profile for the synthetic customer fixture."""
    ingested = load_dataset(str(SAMPLE_DATASET))
    return profile_dataset(ingested.dataframe, ingested.metadata)


@pytest.fixture
def context():
    """Return the synthetic customer context fixture."""
    return load_context(str(SAMPLE_CONTEXT))


def candidate(**overrides):
    """Build a valid default candidate dictionary with overrides."""
    base = {
        "test_id": "customer_id_not_null",
        "test_type": "not_null",
        "column": "customer_id",
        "severity": "high",
        "rationale": "Manual fixture candidate for deterministic validation.",
        "suggested_by": "manual_fixture",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "entry",
    [
        candidate(test_id="not_null", test_type="not_null"),
        candidate(test_id="unique", test_type="unique"),
        candidate(
            test_id="accepted_values",
            test_type="accepted_values",
            column="customer_status",
            parameters={"allowed_values": ["active", "paused", "inactive"]},
        ),
        candidate(
            test_id="numeric_range",
            test_type="numeric_range",
            column="age",
            parameters={"min": 0, "max": 120},
        ),
        candidate(test_id="date_parseable", test_type="date_parseable", column="signup_date"),
        candidate(test_id="date_not_future", test_type="date_not_future", column="last_order_date"),
        candidate(
            test_id="regex_match",
            test_type="regex_match",
            column="email",
            parameters={"pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
        ),
    ],
)
def test_validates_allowed_candidate_types(profile, context, entry):
    """All supported candidate test types should validate when shaped correctly."""
    result = validate_candidate_tests(candidate_entries=[entry], profile=profile, context=context)

    assert result.validated_count == 1
    assert result.rejected_count == 0


@pytest.mark.parametrize(
    ("entries", "reason_code"),
    [
        ([candidate(test_id="dup"), candidate(test_id="dup", column="email")], "duplicate_test_id"),
        ([candidate(test_type="unknown")], "unsupported_test_type"),
        ([candidate(severity="critical")], "unsupported_severity"),
        ([candidate(suggested_by="robot")], "unsupported_suggested_by"),
        ([candidate(column="missing_customer_field")], "unknown_column"),
        ([candidate(test_type="numeric_range", column="email", parameters={"min": 1})], "profile_type_mismatch"),
        ([candidate(test_type="date_not_future", column="age")], "profile_type_mismatch"),
        ([candidate(test_type="regex_match", column="email", parameters={"pattern": "["})], "invalid_regex_pattern"),
        ([candidate(code="print('no')")], "suspicious_execution_field"),
        ([candidate(example_values=["synthetic"] )], "row_level_data_field"),
        ([candidate(extra_contract_field=True)], "unsupported_field"),
        ([candidate(test_type="accepted_values", parameters={"allowed_values": []})], "invalid_parameters"),
        ([candidate(test_type="numeric_range", column="age", parameters={"min": 10, "max": 1})], "invalid_parameters"),
        ([candidate(test_type="regex_match", column="email", parameters={"pattern": 123})], "invalid_parameters"),
    ],
)
def test_rejects_invalid_candidates(profile, entries, reason_code):
    """Invalid schema, parameter, and safety boundary cases should be rejected."""
    result = validate_candidate_tests(candidate_entries=entries, profile=profile)

    assert result.rejected_count >= 1
    reason_codes = {
        reason.reason_code
        for rejected in result.rejected_candidates
        for reason in rejected.rejection_reasons
    }
    assert reason_code in reason_codes


def test_context_fields_to_ignore_can_reject_candidate(profile, context):
    """Context-aware validation should reject fields explicitly marked to ignore."""
    object.__setattr__(context, "fields_to_ignore", ["email"])

    result = validate_candidate_tests(
        candidate_entries=[candidate(test_id="email_not_null", column="email")],
        profile=profile,
        context=context,
    )

    assert result.rejected_count == 1
    assert result.rejected_candidates[0].rejection_reasons[0].reason_code == "column_marked_to_ignore"


def test_duplicate_test_ids_make_all_duplicate_candidates_invalid(profile):
    """Every candidate sharing a duplicated test_id should be rejected for traceability."""
    candidates = [
        {
            "test_id": "duplicate_id",
            "test_type": "not_null",
            "column": "customer_id",
            "severity": "high",
            "rationale": "first duplicate",
            "suggested_by": "manual_fixture",
        },
        {
            "test_id": "duplicate_id",
            "test_type": "unique",
            "column": "customer_id",
            "severity": "high",
            "rationale": "second duplicate",
            "suggested_by": "manual_fixture",
        },
    ]

    result = validate_candidate_tests(candidate_entries=candidates, profile=profile)

    assert result.validated_count == 0
    assert result.rejected_count == 2
    assert all(
        any(reason.reason_code == "duplicate_test_id" for reason in rejected.rejection_reasons)
        for rejected in result.rejected_candidates
    )
