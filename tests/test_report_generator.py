"""Tests for deterministic human review report generation."""

from __future__ import annotations

from pathlib import Path

from data_test_suggestion_agent.candidate_loader import load_candidate_tests
from data_test_suggestion_agent.candidate_validator import (
    build_rejected_suggestions_artifact,
    build_validated_suggestions_artifact,
    validate_candidate_tests,
)
from data_test_suggestion_agent.context_loader import load_context, summarize_context
from data_test_suggestion_agent.evidence_payload import build_test_suggestion_payload
from data_test_suggestion_agent.intake import load_dataset
from data_test_suggestion_agent.profiling import profile_dataset
from data_test_suggestion_agent.report_generator import build_review_report
from data_test_suggestion_agent.test_executor import (
    build_test_execution_results_artifact,
    execute_validated_candidates,
)

SAMPLE_DATASET = Path("sample_data/customers/customers_for_test_suggestions.csv")
SAMPLE_CONTEXT = Path("config/examples/customer_dataset_context.yaml")
MIXED_CANDIDATES = Path("config/examples/customer_candidate_tests_with_rejections.json")


def _profile_payload_context():
    ingested = load_dataset(str(SAMPLE_DATASET))
    profile = profile_dataset(ingested.dataframe, ingested.metadata)
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
    return ingested, profile, payload, context, context_metadata


def _validation_artifacts(profile, context, *, llm_called: bool = False):
    entries = load_candidate_tests(str(MIXED_CANDIDATES))
    result = validate_candidate_tests(
        candidate_entries=entries,
        profile=profile,
        context=context,
    )
    return (
        result,
        build_validated_suggestions_artifact(
            result,
            candidate_tests_generated_by_this_agent=llm_called,
            llm_called=llm_called,
        ),
        build_rejected_suggestions_artifact(
            result,
            candidate_tests_generated_by_this_agent=llm_called,
            llm_called=llm_called,
        ),
    )


def test_builds_profile_only_report_with_boundary_and_dataset_summary():
    """Profile-only report should include safe summaries and no raw sample values."""
    ingested = load_dataset(str(SAMPLE_DATASET))
    profile = profile_dataset(ingested.dataframe, ingested.metadata)
    payload = build_test_suggestion_payload(profile=profile)

    report = build_review_report(
        profile=profile,
        payload=payload,
        artifact_paths={
            "dataset_profile": "/tmp/absolute/path/dataset_profile.json",
            "test_suggestion_payload": "/tmp/absolute/path/test_suggestion_payload.json",
        },
    )

    assert "# Data Test Suggestion Review Report" in report
    assert "This report is for human review." in report
    assert "Candidate tests are not approved tests." in report
    assert "Input file name: customers_for_test_suggestions.csv" in report
    assert "Row count: 24" in report
    assert "Column count: 9" in report
    assert "Candidate validation was not requested." in report
    assert "Candidate execution was not requested." in report
    assert "No candidate generation or validation was requested." in report
    assert "/tmp/absolute/path" not in report
    for forbidden in ("alex.rivera@example.com", "blair.chen@example.com", "CUST-0001"):
        assert forbidden not in report


def test_builds_report_with_context_summary():
    """Human-authored context should be summarized separately from dataset evidence."""
    _, profile, payload, context, context_metadata = _profile_payload_context()

    report = build_review_report(
        profile=profile,
        payload=payload,
        context=context,
        context_metadata=context_metadata,
    )

    assert "## Human-authored context summary" in report
    assert "Dataset name: synthetic_customer_dataset" in report
    assert "Expected grain: one row per synthetic customer" in report
    assert "Business caveat count: 2" in report
    assert "Field note count: 2" in report


def test_builds_report_with_manual_candidate_validation_artifacts():
    """Manual validation artifacts should produce validated and rejected tables."""
    _, profile, payload, context, _ = _profile_payload_context()
    _, validated, rejected = _validation_artifacts(profile, context)

    report = build_review_report(
        profile=profile,
        payload=payload,
        context=context,
        candidate_validation_artifact=validated,
        rejected_suggestions_artifact=rejected,
    )

    assert "Candidate source: Manual candidate file used." in report
    assert "## Validation summary" in report
    assert "Input candidate count: 8" in report
    assert "Validated count: 2" in report
    assert "Rejected count: 6" in report
    assert "customer_id_not_null" in report
    assert "unknown_column" in report
    assert "Candidate tests are not approved tests." in report


def test_builds_report_with_llm_generation_metadata():
    """LLM provenance should be summarized without prompt or response payloads."""
    _, profile, payload, context, _ = _profile_payload_context()
    _, validated, rejected = _validation_artifacts(profile, context, llm_called=True)

    report = build_review_report(
        profile=profile,
        payload=payload,
        context=context,
        llm_metadata={
            "model": "test-model",
            "max_candidates": 8,
            "generated_candidate_count": 8,
            "raw_rows_sent_to_llm": False,
        },
        candidate_validation_artifact=validated,
        rejected_suggestions_artifact=rejected,
    )

    assert "Candidate source: LLM-generated candidates used." in report
    assert "Model name: test-model" in report
    assert "Max candidates: 8" in report
    assert "Generated candidate count: 8" in report
    assert "raw_rows_sent_to_llm = false" in report
    assert "Generated candidates are not approved tests." in report
    assert "raw OpenAI responses" in report
    assert "chain-of-thought" in report


def test_builds_report_with_execution_results():
    """Execution summary should include aggregate-only outcomes."""
    ingested, profile, payload, context, _ = _profile_payload_context()
    result, validated, rejected = _validation_artifacts(profile, context)
    execution_results = execute_validated_candidates(
        dataframe=ingested.dataframe,
        validated_candidates=result.validated_candidates,
    )
    execution = build_test_execution_results_artifact(
        validated_candidate_count=result.validated_count,
        execution_results=execution_results,
    )

    report = build_review_report(
        profile=profile,
        payload=payload,
        context=context,
        candidate_validation_artifact=validated,
        rejected_suggestions_artifact=rejected,
        execution_artifact=execution,
    )

    assert "## Execution summary" in report
    assert "Executed count: 2" in report
    assert "Passed count: 2" in report
    assert "Execution is local-only." in report
    assert "Failed checks are review outcomes, not CLI/process failures." in report
    assert "null_count=0" in report


def test_report_avoids_raw_samples_and_forbidden_authority_claims():
    """Report should not leak raw samples or claim final approval/coverage."""
    _, profile, payload, context, context_metadata = _profile_payload_context()
    report = build_review_report(
        profile=profile,
        payload=payload,
        context=context,
        context_metadata=context_metadata,
    )
    lower_report = report.lower()

    for forbidden in ("alex.rivera@example.com", "blair.chen@example.com", "cust-0001"):
        assert forbidden not in lower_report
    assert "approve automatically" not in lower_report
    assert "coverage is complete" not in lower_report
    assert "tests are guaranteed correct" not in lower_report
    assert "compliant" not in lower_report
    assert "gdpr" not in lower_report
