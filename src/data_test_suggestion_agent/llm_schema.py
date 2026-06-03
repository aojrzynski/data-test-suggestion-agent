"""JSON schema for bounded LLM candidate test generation."""

from __future__ import annotations

from typing import Any

from data_test_suggestion_agent.candidate_models import (
    ALLOWED_SEVERITIES,
    ALLOWED_TEST_TYPES,
)


def build_llm_candidate_response_schema() -> dict[str, Any]:
    """Return the structured-output JSON schema for LLM candidate suggestions.

    The schema constrains the model to the same outer candidate shape accepted
    by deterministic validation. Type-specific parameter rules intentionally
    remain with the local validator, which is the authoritative safety gate.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidate_tests"],
        "properties": {
            "candidate_tests": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "test_id",
                        "test_type",
                        "column",
                        "severity",
                        "parameters",
                        "rationale",
                        "suggested_by",
                    ],
                    "properties": {
                        "test_id": {"type": "string"},
                        "test_type": {
                            "type": "string",
                            "enum": sorted(ALLOWED_TEST_TYPES),
                        },
                        "column": {"type": ["string", "null"]},
                        "severity": {
                            "type": "string",
                            "enum": sorted(ALLOWED_SEVERITIES),
                        },
                        "parameters": {"type": "object"},
                        "rationale": {"type": "string"},
                        "suggested_by": {
                            "type": "string",
                            "enum": ["llm_candidate"],
                        },
                    },
                },
            }
        },
    }
