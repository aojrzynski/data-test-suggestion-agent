"""Deterministic validation for local candidate test suggestions.

This module exists before any LLM generation so future candidates must pass a
strict local contract before review, execution, or reporting can ever happen.
It validates schema, supported test types, safe parameter shapes, dataset column
references, aggregate profile compatibility, and optional human context.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from numbers import Number
from typing import Any

from data_test_suggestion_agent.candidate_models import (
    ALLOWED_CANDIDATE_FIELDS,
    ALLOWED_SEVERITIES,
    ALLOWED_SUGGESTED_BY,
    ALLOWED_TEST_TYPES,
    REQUIRED_CANDIDATE_FIELDS,
    ROW_LEAKAGE_FIELDS,
    SUSPICIOUS_EXECUTION_FIELDS,
    CandidateTestSuggestion,
    CandidateValidationResult,
    RejectedCandidate,
    RejectionReason,
    ValidatedCandidate,
)
from data_test_suggestion_agent.models import DatasetContext, DatasetProfile

MAX_ACCEPTED_VALUES = 50
MAX_REGEX_PATTERN_LENGTH = 250

NO_PARAMETER_TEST_TYPES = {"not_null", "unique", "date_parseable", "date_not_future"}
COLUMN_REQUIRED_TEST_TYPES = ALLOWED_TEST_TYPES


def validate_candidate_tests(
    *,
    candidate_entries: list[dict[str, Any]],
    profile: DatasetProfile,
    context: DatasetContext | None = None,
) -> CandidateValidationResult:
    """Validate candidate suggestions against schema, profile, and context.

    The function does not execute any tests. It only separates locally supplied
    candidates into validation-passed suggestions and rejected suggestions with
    deterministic reasons for human review.
    """
    column_profiles = {column.name: column.to_dict() for column in profile.columns}
    seen_test_ids: set[str] = set()
    # Candidate IDs are traceability keys. If a file repeats an ID, all
    # candidates with that ID are rejected because the validator cannot safely
    # know which duplicate should be authoritative.
    duplicate_test_ids = _duplicate_test_ids(candidate_entries)
    validated: list[ValidatedCandidate] = []
    rejected: list[RejectedCandidate] = []

    for index, raw_candidate in enumerate(candidate_entries):
        reasons: list[RejectionReason] = []
        notes: list[str] = []
        _validate_field_contract(raw_candidate, reasons)

        test_id = _optional_string_value(raw_candidate.get("test_id"))
        test_type = _optional_string_value(raw_candidate.get("test_type"))
        column = _optional_string_value(raw_candidate.get("column"))
        severity = _optional_string_value(raw_candidate.get("severity"))
        rationale = _optional_string_value(raw_candidate.get("rationale"))
        suggested_by = _optional_string_value(raw_candidate.get("suggested_by"))
        parameters = raw_candidate.get("parameters", {})

        if test_id is None or test_id.strip() == "":
            reasons.append(_reason("missing_test_id", "Candidate test_id is required and cannot be blank."))
        elif test_id in duplicate_test_ids or test_id in seen_test_ids:
            reasons.append(_reason("duplicate_test_id", f"Candidate test_id '{test_id}' is duplicated."))
        else:
            seen_test_ids.add(test_id)

        if test_type is None:
            reasons.append(_reason("missing_test_type", "Candidate test_type is required."))
        elif test_type not in ALLOWED_TEST_TYPES:
            reasons.append(_reason("unsupported_test_type", f"Test type '{test_type}' is not supported."))

        if severity is None:
            reasons.append(_reason("missing_severity", "Candidate severity is required."))
        elif severity not in ALLOWED_SEVERITIES:
            reasons.append(_reason("unsupported_severity", f"Severity '{severity}' is not allowed."))

        if suggested_by is None:
            reasons.append(_reason("missing_suggested_by", "Candidate suggested_by is required."))
        elif suggested_by not in ALLOWED_SUGGESTED_BY:
            reasons.append(_reason("unsupported_suggested_by", f"suggested_by '{suggested_by}' is not allowed."))

        if rationale is None or rationale.strip() == "":
            reasons.append(_reason("missing_rationale", "Candidate rationale is required and cannot be blank."))

        if test_type in COLUMN_REQUIRED_TEST_TYPES and (column is None or column.strip() == ""):
            reasons.append(_reason("missing_column", f"Column is required for test type '{test_type}'."))
        elif column is not None and column not in column_profiles:
            reasons.append(_reason("unknown_column", f"Column '{column}' does not exist in the loaded dataset."))

        if not isinstance(parameters, Mapping):
            reasons.append(_reason("invalid_parameters", "Candidate parameters must be an object when provided."))
            parameter_mapping: dict[str, Any] = {}
        else:
            parameter_mapping = dict(parameters)

        if test_type in ALLOWED_TEST_TYPES:
            _validate_parameters(
                test_type=test_type,
                parameters=parameter_mapping,
                reasons=reasons,
            )

        if column in column_profiles and test_type in ALLOWED_TEST_TYPES:
            _validate_profile_compatibility(
                test_type=test_type,
                column=column,
                column_profile=column_profiles[column],
                reasons=reasons,
                notes=notes,
            )
            if context is not None:
                _validate_context(
                    test_type=test_type,
                    column=column,
                    context=context,
                    reasons=reasons,
                    notes=notes,
                )

        if reasons:
            rejected.append(
                RejectedCandidate(
                    candidate_index=index,
                    test_id=test_id,
                    test_type=test_type,
                    column=column,
                    rejection_reasons=reasons,
                )
            )
            continue

        # Construction happens after all checks so the dataclass represents only
        # contract-valid data. It is still not an approved or executable test.
        validated.append(
            ValidatedCandidate(
                candidate=CandidateTestSuggestion(
                    test_id=str(test_id),
                    test_type=str(test_type),
                    column=column,
                    severity=str(severity),
                    parameters=parameter_mapping,
                    rationale=str(rationale),
                    suggested_by=str(suggested_by),
                ),
                validation_notes=notes,
            )
        )

    return CandidateValidationResult(
        input_candidate_count=len(candidate_entries),
        validated_candidates=validated,
        rejected_candidates=rejected,
    )


def build_validated_suggestions_artifact(
    result: CandidateValidationResult,
) -> dict[str, Any]:
    """Build the JSON artifact for validated but unapproved suggestions."""
    return {
        "artifact_name": "validated_test_suggestions",
        "candidate_tests_generated_by_this_agent": False,
        "llm_called": False,
        "validated_candidates_are_approved_tests": False,
        "tests_executed": False,
        "validation_status": "completed",
        "summary": result.summary(),
        "validated_candidates": [candidate.to_dict() for candidate in result.validated_candidates],
    }


def build_rejected_suggestions_artifact(
    result: CandidateValidationResult,
) -> dict[str, Any]:
    """Build the JSON artifact for rejected candidate suggestions."""
    return {
        "artifact_name": "rejected_test_suggestions",
        "candidate_tests_generated_by_this_agent": False,
        "llm_called": False,
        "validated_candidates_are_approved_tests": False,
        "tests_executed": False,
        "validation_status": "completed",
        "summary": result.summary(),
        "rejected_candidates": [candidate.to_dict() for candidate in result.rejected_candidates],
    }


def _validate_field_contract(raw_candidate: dict[str, Any], reasons: list[RejectionReason]) -> None:
    """Reject unsupported, executable, and row-leakage candidate fields."""
    for required_field in sorted(REQUIRED_CANDIDATE_FIELDS - set(raw_candidate)):
        reasons.append(
            _reason(
                "missing_required_field",
                f"Candidate field '{required_field}' is required by the PR #5 contract.",
            )
        )

    for field_name in sorted(raw_candidate):
        if field_name in SUSPICIOUS_EXECUTION_FIELDS:
            # Candidate files are data contracts, never executable recipes.
            reasons.append(
                _reason(
                    "suspicious_execution_field",
                    f"Candidate field '{field_name}' is not allowed because executable/code fields are forbidden.",
                )
            )
        elif field_name in ROW_LEAKAGE_FIELDS:
            reasons.append(
                _reason(
                    "row_level_data_field",
                    f"Candidate field '{field_name}' is not allowed because raw row/example value fields are forbidden.",
                )
            )
        elif field_name not in ALLOWED_CANDIDATE_FIELDS:
            reasons.append(
                _reason(
                    "unsupported_field",
                    f"Candidate field '{field_name}' is not supported by the PR #5 contract.",
                )
            )


def _validate_parameters(
    *,
    test_type: str,
    parameters: dict[str, Any],
    reasons: list[RejectionReason],
) -> None:
    """Validate test-type-specific parameter shape without executing tests."""
    if test_type in NO_PARAMETER_TEST_TYPES:
        _reject_unknown_parameters(test_type, parameters, set(), reasons)
        return

    if test_type == "accepted_values":
        _reject_unknown_parameters(test_type, parameters, {"allowed_values"}, reasons)
        values = parameters.get("allowed_values")
        if not isinstance(values, list) or not values:
            reasons.append(_reason("invalid_parameters", "accepted_values requires a non-empty allowed_values list."))
            return
        if len(values) > MAX_ACCEPTED_VALUES:
            reasons.append(_reason("too_many_allowed_values", f"accepted_values allows at most {MAX_ACCEPTED_VALUES} values."))
        for value in values:
            if not _is_allowed_literal(value):
                reasons.append(_reason("invalid_parameters", "allowed_values entries must be strings, numbers, booleans, or null."))
                break
        # The values are accepted only because the human/fixture supplied them;
        # this PR never infers final accepted values from raw source data.
        return

    if test_type == "numeric_range":
        _reject_unknown_parameters(test_type, parameters, {"min", "max"}, reasons)
        has_min = "min" in parameters
        has_max = "max" in parameters
        if not has_min and not has_max:
            reasons.append(_reason("invalid_parameters", "numeric_range requires min and/or max."))
            return
        min_value = parameters.get("min")
        max_value = parameters.get("max")
        if has_min and not _is_number(min_value):
            reasons.append(_reason("invalid_parameters", "numeric_range min must be a number."))
        if has_max and not _is_number(max_value):
            reasons.append(_reason("invalid_parameters", "numeric_range max must be a number."))
        if _is_number(min_value) and _is_number(max_value) and min_value > max_value:
            reasons.append(_reason("invalid_parameters", "numeric_range min cannot be greater than max."))
        return

    if test_type == "regex_match":
        _reject_unknown_parameters(test_type, parameters, {"pattern"}, reasons)
        pattern = parameters.get("pattern")
        if not isinstance(pattern, str):
            reasons.append(_reason("invalid_parameters", "regex_match requires a string pattern."))
            return
        if len(pattern) > MAX_REGEX_PATTERN_LENGTH:
            reasons.append(_reason("regex_pattern_too_long", f"regex_match pattern cannot exceed {MAX_REGEX_PATTERN_LENGTH} characters."))
            return
        try:
            re.compile(pattern)
        except re.error as exc:
            reasons.append(_reason("invalid_regex_pattern", f"regex_match pattern does not compile: {exc}."))
        return


def _validate_profile_compatibility(
    *,
    test_type: str,
    column: str,
    column_profile: dict[str, Any],
    reasons: list[RejectionReason],
    notes: list[str],
) -> None:
    """Validate candidates against aggregate-only profile evidence."""
    profile_type = column_profile.get("profile_type")
    if test_type == "numeric_range" and profile_type != "numeric":
        reasons.append(_reason("profile_type_mismatch", f"numeric_range requires a numeric column, but '{column}' is profiled as {profile_type}."))
    if test_type in {"date_parseable", "date_not_future"} and profile_type in {"numeric", "boolean"}:
        reasons.append(_reason("profile_type_mismatch", f"{test_type} requires a date-like or text column, but '{column}' is profiled as {profile_type}."))
    if test_type == "accepted_values" and not column_profile.get("low_cardinality_candidate", False):
        notes.append("column_not_profiled_as_low_cardinality")


def _validate_context(
    *,
    test_type: str,
    column: str,
    context: DatasetContext,
    reasons: list[RejectionReason],
    notes: list[str],
) -> None:
    """Apply small deterministic context-aware checks and notes."""
    if column in context.fields_to_ignore:
        reasons.append(_reason("column_marked_to_ignore", f"Column '{column}' is marked to ignore in human-authored context."))
        return
    if test_type == "accepted_values" and column in context.known_categorical_fields:
        notes.append("supported_by_context_known_categorical_field")
    if test_type == "unique" and column in context.known_id_fields:
        notes.append("supported_by_context_known_id_field")


def _reject_unknown_parameters(
    test_type: str,
    parameters: dict[str, Any],
    allowed: set[str],
    reasons: list[RejectionReason],
) -> None:
    """Reject parameter names outside the current test-type contract."""
    unknown = sorted(key for key in parameters if key not in allowed)
    if unknown:
        joined = ", ".join(unknown)
        reasons.append(_reason("unknown_parameter", f"{test_type} does not support parameter(s): {joined}."))


def _duplicate_test_ids(candidate_entries: list[dict[str, Any]]) -> set[str]:
    """Return non-blank candidate IDs that appear more than once."""
    counts: dict[str, int] = {}
    for candidate in candidate_entries:
        test_id = _optional_string_value(candidate.get("test_id"))
        if test_id is None or test_id.strip() == "":
            continue
        counts[test_id] = counts.get(test_id, 0) + 1
    return {test_id for test_id, count in counts.items() if count > 1}


def _optional_string_value(value: Any) -> str | None:
    """Return a string value or ``None`` for non-string/null values."""
    if isinstance(value, str):
        return value
    return None


def _is_allowed_literal(value: Any) -> bool:
    """Return whether a value is JSON-literal-like and safe in parameters."""
    return value is None or isinstance(value, (str, int, float, bool))


def _is_number(value: Any) -> bool:
    """Return whether a value is a non-boolean number."""
    return isinstance(value, Number) and not isinstance(value, bool)


def _reason(reason_code: str, message: str) -> RejectionReason:
    """Create a rejection reason."""
    return RejectionReason(reason_code=reason_code, message=message)
