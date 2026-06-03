"""Tests for bounded LLM prompt and schema construction."""

from __future__ import annotations

import json

from data_test_suggestion_agent.context_loader import load_context, summarize_context
from data_test_suggestion_agent.evidence_payload import build_test_suggestion_payload
from data_test_suggestion_agent.intake import load_dataset
from data_test_suggestion_agent.llm_prompt_builder import (
    build_llm_candidate_prompt,
    sanitize_payload_for_llm,
)
from data_test_suggestion_agent.llm_schema import build_llm_candidate_response_schema
from data_test_suggestion_agent.profiling import profile_dataset


def _sample_payload() -> dict[str, object]:
    ingested = load_dataset("sample_data/customers/customers_for_test_suggestions.csv")
    profile = profile_dataset(ingested.dataframe, ingested.metadata)
    context = load_context("config/examples/customer_dataset_context.yaml")
    context_metadata = summarize_context(
        context=context,
        context_path="config/examples/customer_dataset_context.yaml",
        dataset_columns=ingested.metadata.columns,
    )
    return build_test_suggestion_payload(
        profile=profile,
        context=context,
        context_metadata=context_metadata,
    )


def test_prompt_uses_safe_payload_and_contains_boundaries():
    """Prompt should describe the bounded non-authoritative LLM role."""
    prompt = build_llm_candidate_prompt(
        test_suggestion_payload=_sample_payload(),
        max_candidates=8,
    )
    prompt_text = json.dumps(prompt)

    assert "candidate data test suggestions only" in prompt_text
    assert "not authoritative" in prompt_text
    assert "suggested_by" in prompt_text
    assert "llm_candidate" in prompt_text
    for test_type in (
        "not_null",
        "unique",
        "accepted_values",
        "numeric_range",
        "date_parseable",
        "date_not_future",
        "regex_match",
    ):
        assert test_type in prompt_text
    assert "Do not analyze raw rows" in prompt_text
    assert "Do not generate code, SQL" in prompt_text
    assert "legal, compliance, privacy" in prompt_text
    assert "Deterministic local validation may reject" in prompt_text
    assert "alex.rivera@example.com" not in prompt_text
    assert "blair.chen@example.com" not in prompt_text
    assert "CUST-0001" not in prompt_text


def test_prompt_sanitizes_absolute_input_path_but_keeps_useful_metadata():
    """LLM prompt input should avoid local paths while preserving safe evidence."""
    payload = _sample_payload()
    payload["dataset_evidence"]["metadata"]["input_path"] = (
        "/Users/example/private/customers_for_test_suggestions.csv"
    )

    prompt = build_llm_candidate_prompt(
        test_suggestion_payload=payload,
        max_candidates=8,
    )
    prompt_text = json.dumps(prompt)

    assert "/Users/example/private/customers_for_test_suggestions.csv" not in prompt_text
    assert payload["dataset_evidence"]["metadata"]["input_path"] == (
        "/Users/example/private/customers_for_test_suggestions.csv"
    )
    assert "customers_for_test_suggestions.csv" in prompt_text
    assert "customer_id" in prompt_text
    assert "alex.rivera@example.com" not in prompt_text
    assert "blair.chen@example.com" not in prompt_text
    assert "CUST-0001" not in prompt_text


def test_sanitize_payload_for_llm_does_not_mutate_original_payload():
    """Sanitization should remove only local path evidence from a copied payload."""
    payload = _sample_payload()
    payload["dataset_evidence"]["metadata"]["input_path"] = "/tmp/private/input.csv"

    sanitized = sanitize_payload_for_llm(payload)

    assert "input_path" not in sanitized["dataset_evidence"]["metadata"]
    assert payload["dataset_evidence"]["metadata"]["input_path"] == "/tmp/private/input.csv"
    assert sanitized["dataset_evidence"]["metadata"]["file_name"] == (
        payload["dataset_evidence"]["metadata"]["file_name"]
    )
    assert sanitized["dataset_evidence"]["profile_summary"]["column_names"] == (
        payload["dataset_evidence"]["profile_summary"]["column_names"]
    )


def test_llm_schema_requires_candidate_tests_and_disallows_extra_fields():
    """Structured output schema should constrain the shared outer shape."""
    schema = build_llm_candidate_response_schema()

    assert schema["required"] == ["candidate_tests"]
    assert schema["additionalProperties"] is False
    candidate_schema = schema["properties"]["candidate_tests"]["items"]
    assert candidate_schema["additionalProperties"] is False
    assert set(candidate_schema["required"]) == {
        "test_id",
        "test_type",
        "column",
        "severity",
        "parameters",
        "rationale",
        "suggested_by",
    }
    assert candidate_schema["properties"]["suggested_by"]["enum"] == ["llm_candidate"]
