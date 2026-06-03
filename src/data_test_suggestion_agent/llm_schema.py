"""JSON schema for bounded LLM candidate test generation.

The schema constrains structured model output, but it does not replace the
local deterministic validator. Generated candidates still pass through the same
candidate contract, profile compatibility, and context checks as manual files.
"""

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
    remain with the local validator, which is the required safety gate.
    """
    return {
        "type": "object",
        # Disallow extra top-level fields in structured output so unexpected
        # model text cannot masquerade as part of the candidate artifact.
        "additionalProperties": False,
        "required": ["candidate_tests"],
        "properties": {
            "candidate_tests": {
                "type": "array",
                "items": {
                    "type": "object",
                    # Candidate objects also reject extra fields at schema time;
                    # executable-field and row-leakage checks still run locally.
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
                        # Test-type-specific parameter validation stays in
                        # candidate_validator.py, the final deterministic gate.
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
