"""Tests for optional LLM candidate generation helpers."""

from __future__ import annotations

import builtins
import json

import pytest

from data_test_suggestion_agent.llm_candidate_generator import (
    CandidateGenerationError,
    generate_candidate_tests_with_openai,
    parse_llm_candidate_response_text,
)


class _FakeResponse:
    def __init__(self, output_text: str):
        self.output_text = output_text


class _FakeResponses:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class _FakeClient:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self.responses = _FakeResponses(response=response, error=error)


def test_parse_valid_llm_response_and_normalizes_missing_parameters():
    """Only omitted parameters should be normalized before validation."""
    parsed = parse_llm_candidate_response_text(
        json.dumps(
            {
                "candidate_tests": [
                    {
                        "test_id": "customer_id_unique",
                        "test_type": "unique",
                        "column": "customer_id",
                        "severity": "high",
                        "rationale": "ID-like field in safe evidence.",
                        "suggested_by": "llm_candidate",
                    }
                ]
            }
        )
    )

    assert parsed[0]["parameters"] == {}


@pytest.mark.parametrize(
    "raw_text, expected",
    [
        ("{not json", "Malformed candidate JSON"),
        ("[]", "top level must be an object"),
        (json.dumps({}), "must include 'candidate_tests'"),
        (json.dumps({"candidate_tests": {}}), "must be a list"),
        (json.dumps({"candidate_tests": ["bad"]}), "must be an object"),
    ],
)
def test_parse_rejects_malformed_outer_shapes(raw_text, expected):
    """Malformed LLM outer shapes should fail before artifact writing."""
    with pytest.raises(CandidateGenerationError, match=expected):
        parse_llm_candidate_response_text(raw_text)


def test_parse_does_not_repair_invalid_type_or_unknown_column():
    """Semantic issues should be left for deterministic validation."""
    parsed = parse_llm_candidate_response_text(
        json.dumps(
            {
                "candidate_tests": [
                    {
                        "test_id": "bad",
                        "test_type": "made_up_type",
                        "column": "not_a_column",
                        "severity": "high",
                        "parameters": {},
                        "rationale": "Bad but parseable.",
                        "suggested_by": "llm_candidate",
                    }
                ]
            }
        )
    )

    assert parsed[0]["test_type"] == "made_up_type"
    assert parsed[0]["column"] == "not_a_column"


def test_missing_api_key_fails_cleanly(monkeypatch):
    """OpenAI generation should require OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(CandidateGenerationError, match="OPENAI_API_KEY"):
        generate_candidate_tests_with_openai(
            test_suggestion_payload={},
            model="test-model",
            max_candidates=1,
        )


def test_missing_openai_package_fails_cleanly(monkeypatch):
    """Lazy import should report the optional llm extra when OpenAI is absent."""
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(CandidateGenerationError, match="optional LLM extra"):
        generate_candidate_tests_with_openai(
            test_suggestion_payload={},
            model="test-model",
            max_candidates=1,
            api_key="test-key",
        )


def test_fake_successful_client_returns_parsed_candidates():
    """Fake clients avoid live OpenAI calls in tests."""
    response = _FakeResponse(
        json.dumps(
            {
                "candidate_tests": [
                    {
                        "test_id": "customer_id_not_null",
                        "test_type": "not_null",
                        "column": "customer_id",
                        "severity": "high",
                        "parameters": {},
                        "rationale": "Important field in safe evidence.",
                        "suggested_by": "llm_candidate",
                    }
                ]
            }
        )
    )
    client = _FakeClient(response=response)

    candidates = generate_candidate_tests_with_openai(
        test_suggestion_payload={"payload_metadata": {"contains_raw_rows": False}},
        model="test-model",
        max_candidates=2,
        api_key="test-key",
        client=client,
    )

    assert candidates[0]["test_id"] == "customer_id_not_null"
    assert client.responses.calls[0]["model"] == "test-model"
    assert client.responses.calls[0]["text"]["format"]["type"] == "json_schema"


def test_fake_api_error_is_clean_candidate_generation_error():
    """SDK/network errors should be converted to user-facing errors."""
    client = _FakeClient(error=RuntimeError("boom"))

    with pytest.raises(CandidateGenerationError, match="OpenAI candidate generation failed"):
        generate_candidate_tests_with_openai(
            test_suggestion_payload={},
            model="test-model",
            max_candidates=1,
            api_key="test-key",
            client=client,
        )
