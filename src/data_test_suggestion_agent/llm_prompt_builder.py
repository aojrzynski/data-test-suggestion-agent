"""Prompt construction for bounded LLM candidate test generation."""

from __future__ import annotations

import json
from typing import Any

from data_test_suggestion_agent.candidate_models import ALLOWED_TEST_TYPES
from data_test_suggestion_agent.llm_schema import build_llm_candidate_response_schema

SYSTEM_PROMPT = """You are helping a local-first data test suggestion agent.
Produce candidate data test suggestions only. You are not authoritative.
You must not approve tests, claim coverage is complete, or make legal, compliance, privacy, or governance verdicts.
Use only the supplied safe evidence payload. Do not invent columns.
Do not analyze raw rows, example records, source files, top values, or distinct value lists.
Do not include raw data values or example records in rationales or parameters.
Do not generate code, SQL, expressions, eval text, scripts, shell commands, or executable instructions.
Be conservative and prefer fewer high-confidence candidates over many weak candidates.
Only propose accepted_values when allowed values are clearly supported by human-authored context.
Every candidate must set suggested_by to "llm_candidate".
Deterministic local validation may reject any candidate you return.
Generated candidates are not approved tests; a human reviewer decides what becomes official."""


def build_llm_candidate_prompt(
    *,
    test_suggestion_payload: dict[str, Any],
    max_candidates: int,
) -> list[dict[str, str]]:
    """Build Responses API input messages from safe evidence payload only.

    The caller passes ``test_suggestion_payload.json`` data rather than a
    dataframe or source file so raw rows are never sent to the LLM. The prompt
    repeats that structured output is still subject to deterministic validation.
    """
    schema = build_llm_candidate_response_schema()
    user_payload = {
        "task": "Generate structured candidate data tests from the safe evidence payload only.",
        "max_candidates": max_candidates,
        "allowed_test_types": sorted(ALLOWED_TEST_TYPES),
        "required_output_shape": {"candidate_tests": ["candidate objects"]},
        "schema": schema,
        "safe_evidence_payload": test_suggestion_payload,
        "boundaries": {
            "raw_rows_sent": False,
            "example_values_sent": False,
            "top_values_sent": False,
            "distinct_value_lists_sent": False,
            "source_files_sent": False,
            "approved_tests": False,
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(user_payload, indent=2, sort_keys=True),
        },
    ]
