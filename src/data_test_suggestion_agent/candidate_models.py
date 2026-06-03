"""Typed models for local candidate test suggestion validation.

Candidate suggestions use a narrow data-only contract shared by manual files
and optional LLM generation. Execution, approval, and report generation remain
separate stages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# These are suggestion types accepted by validation. They are not execution
# permissions by themselves; execution is a later opt-in stage.
ALLOWED_TEST_TYPES = {
    "not_null",
    "unique",
    "accepted_values",
    "numeric_range",
    "date_parseable",
    "date_not_future",
    "regex_match",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}
# Provenance is recorded because manual and LLM candidates share one validator,
# and reviewers need to distinguish where each suggestion originated.
ALLOWED_SUGGESTED_BY = {"manual_fixture", "llm_candidate", "human_reviewer"}

REQUIRED_CANDIDATE_FIELDS = {
    "test_id",
    "test_type",
    "column",
    "severity",
    "rationale",
    "suggested_by",
}
OPTIONAL_CANDIDATE_FIELDS = {"parameters"}
ALLOWED_CANDIDATE_FIELDS = REQUIRED_CANDIDATE_FIELDS | OPTIONAL_CANDIDATE_FIELDS

# Arbitrary executable text is not part of the candidate contract. Manual and
# LLM-generated suggestions must remain data-only inputs for validation.
SUSPICIOUS_EXECUTION_FIELDS = {
    "code",
    "python",
    "sql",
    "expression",
    "eval",
    "function_body",
    "script",
    "command",
}

# Candidate validation must not become a back door for row-level source data.
ROW_LEAKAGE_FIELDS = {
    "raw_rows",
    "sample_records",
    "example_values",
    "top_values",
    "distinct_values",
    "source_data_preview",
}


@dataclass(frozen=True)
class CandidateTestSuggestion:
    """A candidate test suggestion that has passed schema-level coercion.

    Passing this model does not mean the candidate is approved, correct, or
    executable. The candidate model is distinct from an approved test and from
    an executed test; it only means the local deterministic validation layer
    accepted the suggestion contract for later human review.
    """

    test_id: str
    test_type: str
    column: str | None
    severity: str
    parameters: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    suggested_by: str = "manual_fixture"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable candidate dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class RejectionReason:
    """A deterministic reason explaining why a candidate was rejected."""

    reason_code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable rejection reason."""
        return asdict(self)


@dataclass(frozen=True)
class ValidatedCandidate:
    """A validated candidate plus non-authoritative validation notes."""

    candidate: CandidateTestSuggestion
    validation_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the validated candidate artifact entry."""
        payload = self.candidate.to_dict()
        payload["validation_notes"] = list(self.validation_notes)
        return payload


@dataclass(frozen=True)
class RejectedCandidate:
    """A rejected candidate summary suitable for safe JSON artifacts."""

    candidate_index: int
    test_id: str | None
    test_type: str | None
    column: str | None
    rejection_reasons: list[RejectionReason]

    def to_dict(self) -> dict[str, Any]:
        """Return the rejected candidate artifact entry."""
        return {
            "candidate_index": self.candidate_index,
            "test_id": self.test_id,
            "test_type": self.test_type,
            "column": self.column,
            "rejection_reasons": [reason.to_dict() for reason in self.rejection_reasons],
        }


@dataclass(frozen=True)
class CandidateValidationResult:
    """Deterministic validation result for manual or generated candidates.

    Validated candidates remain unapproved suggestions. This result is a safety
    gate for candidate suggestion workflows, not an execution or governance
    decision.
    """

    input_candidate_count: int
    validated_candidates: list[ValidatedCandidate]
    rejected_candidates: list[RejectedCandidate]

    @property
    def validated_count(self) -> int:
        """Return the number of candidates that passed validation."""
        return len(self.validated_candidates)

    @property
    def rejected_count(self) -> int:
        """Return the number of candidates rejected by validation."""
        return len(self.rejected_candidates)

    def summary(self) -> dict[str, int]:
        """Return summary counts for trace and artifacts."""
        return {
            "input_candidate_count": self.input_candidate_count,
            "validated_count": self.validated_count,
            "rejected_count": self.rejected_count,
        }
