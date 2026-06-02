"""Build local-only evidence payloads for future test suggestion workflows.

This module deliberately stops at deterministic, reviewable evidence assembly.
It does not call an LLM, infer official tests, generate candidate tests, or
execute code. Keeping payload construction separate makes the future boundary
between local evidence and optional bounded generation explicit and testable.
"""

from __future__ import annotations

from typing import Any

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.models import DatasetContext, DatasetProfile

PAYLOAD_NAME = "test_suggestion_payload"
PAYLOAD_VERSION = "0.1.0"
AGENT_NAME = "data-test-suggestion-agent"

# These names are intentionally excluded from profile summaries and checked in
# tests. They describe row-level leakage patterns that are out of scope for this
# local evidence payload and any future LLM handoff.
DISALLOWED_ROW_VALUE_KEYS = {
    "raw_rows",
    "records",
    "sample_records",
    "sampled_records",
    "data_preview",
    "source_data_preview",
    "example_values",
    "examples",
    "sample_values",
    "top_values",
    "distinct_values",
    "distinct_value_lists",
}


def build_test_suggestion_payload(
    *,
    profile: DatasetProfile,
    context: DatasetContext | None = None,
    context_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic safe evidence payload for local review.

    The payload is intentionally marked as not LLM-ready in this PR because no
    prompt contract, bounded generation, execution, or reviewer approval flow
    exists yet. It gathers only aggregate profile evidence plus optional
    human-authored context summary, and it records that no candidate tests were
    generated.
    """
    return {
        "payload_metadata": _payload_metadata(),
        "authority_boundary": _authority_boundary(),
        "dataset_evidence": summarize_profile_for_payload(profile),
        "human_context": summarize_context_for_payload(
            context=context,
            context_metadata=context_metadata,
        ),
        "future_generation_guidance": {
            "allowed_future_output": "candidate_test_suggestions_only",
            "disallowed_future_output": [
                "approved_tests",
                "compliance_verdicts",
                "legal_verdicts",
                "arbitrary_code",
                "raw_row_analysis",
            ],
        },
    }


def summarize_profile_for_payload(profile: DatasetProfile) -> dict[str, Any]:
    """Return profile evidence using only aggregate, row-safe fields.

    ``DatasetProfile`` already avoids raw rows, examples, top values, and
    distinct value lists. This extra projection documents the boundary for the
    future generation input and prevents accidental addition of preview-like
    fields to the payload if the profile artifact evolves.
    """
    profile_dict = profile.to_dict()
    columns = [
        _without_disallowed_keys(column)
        for column in profile_dict.get("columns", [])
    ]
    return {
        "metadata": profile.dataset_metadata.to_dict(),
        "profile_summary": {
            "row_count": profile.row_count,
            "column_count": profile.column_count,
            "column_names": list(profile.dataset_metadata.columns),
        },
        "columns": columns,
    }


def summarize_context_for_payload(
    *,
    context: DatasetContext | None,
    context_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return safe human-authored context summary for the payload.

    Context is represented separately from ``dataset_profile.json`` because it
    is reviewer-supplied metadata rather than deterministic source-data
    evidence. Field lists and notes are acceptable here because they come from
    validated human-authored YAML, not from copied dataset values.
    """
    if context is None:
        return {
            "provided": False,
            "important_fields": [],
            "known_id_fields": [],
            "known_date_fields": [],
            "known_categorical_fields": [],
            "fields_to_ignore": [],
            "business_caveat_count": 0,
            "field_note_count": 0,
            "missing_context_fields": [],
        }

    missing_context_fields = []
    context_warning_count = 0
    if context_metadata is not None:
        missing_context_fields = list(context_metadata.get("missing_context_fields", []))
        context_warning_count = int(context_metadata.get("context_warning_count", 0))

    return {
        "provided": True,
        "dataset_name": context.dataset_name,
        "dataset_purpose": context.dataset_purpose,
        "expected_grain": context.expected_grain,
        "important_fields": list(context.important_fields),
        "known_id_fields": list(context.known_id_fields),
        "known_date_fields": list(context.known_date_fields),
        "known_categorical_fields": list(context.known_categorical_fields),
        "fields_to_ignore": list(context.fields_to_ignore),
        "business_caveat_count": len(context.business_caveats),
        "business_caveats": list(context.business_caveats),
        "field_note_count": len(context.field_notes),
        "field_notes": dict(context.field_notes),
        "preferred_strictness": context.preferred_strictness,
        "missing_context_fields": missing_context_fields,
        "context_warning_count": context_warning_count,
    }


def _payload_metadata() -> dict[str, Any]:
    """Return metadata describing this local evidence payload."""
    return {
        "payload_name": PAYLOAD_NAME,
        "payload_version": PAYLOAD_VERSION,
        "agent_name": AGENT_NAME,
        "package_version": __version__,
        "purpose": "Local reviewable evidence for future candidate data test suggestion.",
        "contains_raw_rows": False,
        "contains_example_values": False,
        "contains_top_values": False,
        "contains_distinct_value_lists": False,
        "llm_ready": False,
    }


def _authority_boundary() -> dict[str, Any]:
    """Return explicit safety and authority limits for this PR's artifact."""
    return {
        "candidate_tests_generated": False,
        "llm_called": False,
        "human_review_required": True,
        "test_decisions_are_not_made": True,
        "notes": [
            "This payload is constructed locally and is not sent anywhere by this CLI.",
            "It contains aggregate dataset profile evidence and optional human-authored context only.",
            "It must not be treated as approved, complete, or correct test coverage.",
            "Candidate test generation, execution, and reporting are not implemented in this PR; manually supplied candidates may be validated separately.",
        ],
    }


def _without_disallowed_keys(value: dict[str, Any]) -> dict[str, Any]:
    """Return a dictionary with row-level leakage keys removed."""
    return {
        key: item
        for key, item in value.items()
        if key not in DISALLOWED_ROW_VALUE_KEYS
    }
