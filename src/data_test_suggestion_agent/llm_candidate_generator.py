"""Optional OpenAI-backed bounded candidate test generation."""

from __future__ import annotations

import json
import os
from typing import Any

from data_test_suggestion_agent.candidate_loader import (
    CandidateLoadError,
    parse_candidate_tests_json_text,
)
from data_test_suggestion_agent.llm_prompt_builder import build_llm_candidate_prompt
from data_test_suggestion_agent.llm_schema import build_llm_candidate_response_schema


class CandidateGenerationError(ValueError):
    """Expected user-facing LLM candidate generation failure."""


def parse_llm_candidate_response_text(response_text: str) -> list[dict[str, Any]]:
    """Parse and safely normalize LLM candidate JSON text.

    Only omitted ``parameters`` fields are normalized to ``{}``. Invalid test
    types, unknown columns, missing provenance, and type-specific parameter
    issues are deliberately left untouched for deterministic validation.
    """
    try:
        return parse_candidate_tests_json_text(
            response_text,
            source_label="LLM candidate response",
            normalize_missing_parameters=True,
        )
    except CandidateLoadError as exc:
        raise CandidateGenerationError(str(exc)) from exc


def build_llm_candidate_tests_artifact(
    *,
    candidate_tests: list[dict[str, Any]],
    source_payload_artifact: str,
    model: str,
    max_candidates: int,
) -> dict[str, Any]:
    """Build the safe LLM candidate artifact without raw responses or prompts.

    Generated candidates remain suggestions only. They are written in the same
    schema-shaped form that will immediately pass through deterministic
    validation; no chain-of-thought or raw OpenAI response is persisted.
    """
    return {
        "artifact_name": "llm_candidate_tests",
        "candidate_tests_generated_by_this_agent": True,
        "llm_called": True,
        "generation_status": "completed",
        "source_payload_artifact": source_payload_artifact,
        "model": model,
        "max_candidates": max_candidates,
        "raw_rows_included": False,
        "example_values_included": False,
        "top_values_included": False,
        "distinct_value_lists_included": False,
        "candidate_count": len(candidate_tests),
        "candidate_tests": candidate_tests,
    }


def generate_candidate_tests_with_openai(
    *,
    test_suggestion_payload: dict[str, Any],
    model: str,
    max_candidates: int,
    api_key: str | None = None,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Generate candidate tests with the OpenAI Responses API.

    OpenAI is an optional dependency for local-first deterministic usage, so the
    SDK import is lazy and only happens when LLM generation is requested. Tests
    can pass a fake client to avoid live API calls.
    """
    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_api_key:
        raise CandidateGenerationError(
            "OPENAI_API_KEY is required when --generate-candidates is used."
        )

    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise CandidateGenerationError(
                "OpenAI SDK is not installed. Install the optional LLM extra with "
                'pip install -e ".[dev,llm]".'
            ) from exc
        client = OpenAI(api_key=resolved_api_key)

    messages = build_llm_candidate_prompt(
        test_suggestion_payload=test_suggestion_payload,
        max_candidates=max_candidates,
    )
    schema = build_llm_candidate_response_schema()
    try:
        response = client.responses.create(
            model=model,
            input=messages,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "data_test_candidate_tests",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
    except Exception as exc:  # noqa: BLE001 - convert SDK/network failures for CLI users.
        raise CandidateGenerationError(f"OpenAI candidate generation failed: {exc}") from exc

    response_text = _extract_response_text(response)
    return parse_llm_candidate_response_text(response_text)


def _extract_response_text(response: Any) -> str:
    """Extract JSON text from a Responses API object or test fake."""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output_parsed = getattr(response, "output_parsed", None)
    if isinstance(output_parsed, dict):
        return json.dumps(output_parsed)

    if isinstance(response, dict):
        if isinstance(response.get("output_text"), str):
            return str(response["output_text"])
        if isinstance(response.get("output_parsed"), dict):
            return json.dumps(response["output_parsed"])

    raise CandidateGenerationError(
        "OpenAI candidate generation response did not include JSON output text."
    )
