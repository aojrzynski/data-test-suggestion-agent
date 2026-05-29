"""Tests for deterministic safe evidence payload construction."""

from __future__ import annotations

import json
from pathlib import Path

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.context_loader import load_context, summarize_context
from data_test_suggestion_agent.evidence_payload import build_test_suggestion_payload
from data_test_suggestion_agent.intake import load_dataset
from data_test_suggestion_agent.profiling import profile_dataset

SAMPLE_DATASET = Path("sample_data/customers/customers_for_test_suggestions.csv")
SAMPLE_CONTEXT = Path("config/examples/customer_dataset_context.yaml")
RAW_SAMPLE_VALUES = [
    "alex.rivera@example.com",
    "blair.chen@example.com",
    "CUST-0001",
]
ROW_LEAKAGE_KEYS = [
    "raw_rows",
    "sampled_records",
    "sample_records",
    "example_values",
    "top_values",
    "distinct_values",
    "distinct_value_lists",
    "source_data_preview",
]


def _profile_sample_dataset():
    """Return the sample dataset profile used by payload tests."""
    ingested = load_dataset(str(SAMPLE_DATASET))
    return ingested, profile_dataset(ingested.dataframe, ingested.metadata)


def test_payload_builder_without_context_includes_safe_boundaries_and_evidence():
    """A payload without context should contain aggregate evidence only."""
    _ingested, profile = _profile_sample_dataset()

    payload = build_test_suggestion_payload(profile=profile)

    assert payload["payload_metadata"] == {
        "payload_name": "test_suggestion_payload",
        "payload_version": "0.1.0",
        "agent_name": "data-test-suggestion-agent",
        "package_version": __version__,
        "purpose": "Local reviewable evidence for future candidate data test suggestion.",
        "contains_raw_rows": False,
        "contains_example_values": False,
        "contains_top_values": False,
        "contains_distinct_value_lists": False,
        "llm_ready": False,
    }
    assert payload["authority_boundary"]["llm_called"] is False
    assert payload["authority_boundary"]["candidate_tests_generated"] is False
    assert payload["authority_boundary"]["human_review_required"] is True
    assert payload["authority_boundary"]["test_decisions_are_not_made"] is True
    assert payload["human_context"]["provided"] is False
    assert payload["human_context"]["business_caveat_count"] == 0
    assert payload["human_context"]["field_note_count"] == 0

    evidence = payload["dataset_evidence"]
    assert evidence["metadata"]["file_name"] == SAMPLE_DATASET.name
    assert evidence["profile_summary"]["row_count"] == 24
    assert evidence["profile_summary"]["column_count"] == 9
    assert "email" in evidence["profile_summary"]["column_names"]
    email_profile = next(column for column in evidence["columns"] if column["name"] == "email")
    assert email_profile["pandas_dtype"] == "object"
    assert email_profile["null_count"] == 0
    assert email_profile["unique_count"] == 24


def test_payload_builder_with_context_includes_human_authored_summary():
    """Validated human context should be summarized separately from profile evidence."""
    ingested, profile = _profile_sample_dataset()
    context = load_context(str(SAMPLE_CONTEXT))
    context_metadata = summarize_context(
        context=context,
        context_path=str(SAMPLE_CONTEXT),
        dataset_columns=ingested.metadata.columns,
    )

    payload = build_test_suggestion_payload(
        profile=profile,
        context=context,
        context_metadata=context_metadata,
    )

    human_context = payload["human_context"]
    assert human_context["provided"] is True
    assert human_context["dataset_name"] == "synthetic_customer_dataset"
    assert human_context["expected_grain"] == "one row per synthetic customer"
    assert human_context["important_fields"] == ["customer_id", "email", "signup_date"]
    assert human_context["known_id_fields"] == ["customer_id"]
    assert human_context["known_date_fields"] == ["signup_date", "last_order_date"]
    assert human_context["known_categorical_fields"] == [
        "customer_status",
        "marketing_consent",
        "country",
    ]
    assert human_context["fields_to_ignore"] == []
    assert human_context["business_caveat_count"] == 2
    assert human_context["field_note_count"] == 2
    assert human_context["preferred_strictness"] == "standard"
    assert human_context["missing_context_fields"] == []
    assert payload["authority_boundary"]["llm_called"] is False
    assert payload["authority_boundary"]["candidate_tests_generated"] is False


def test_payload_does_not_include_raw_rows_or_sample_values():
    """The payload should not leak raw sample values or preview-oriented keys."""
    _ingested, profile = _profile_sample_dataset()

    payload_text = json.dumps(build_test_suggestion_payload(profile=profile), sort_keys=True)

    for raw_value in RAW_SAMPLE_VALUES:
        assert raw_value not in payload_text
    for leakage_key in ROW_LEAKAGE_KEYS:
        assert f'"{leakage_key}":' not in payload_text
    assert "customer_id" in payload_text
    assert "email" in payload_text
