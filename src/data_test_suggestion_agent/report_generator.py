"""Deterministic Markdown report generation for human review.

The report is built only from in-memory aggregate artifacts produced earlier in
one CLI run. It never calls an LLM, never re-profiles data, and never reads raw
rows or raw failing values back from disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.models import DatasetContext, DatasetProfile

AGENT_NAME = "data-test-suggestion-agent"


def build_review_report(
    *,
    profile: DatasetProfile,
    payload: dict[str, Any],
    context: DatasetContext | None = None,
    context_metadata: dict[str, Any] | None = None,
    llm_metadata: dict[str, Any] | None = None,
    candidate_validation_artifact: dict[str, Any] | None = None,
    rejected_suggestions_artifact: dict[str, Any] | None = None,
    execution_artifact: dict[str, Any] | None = None,
    artifact_paths: dict[str, str] | None = None,
) -> str:
    """Build a deterministic Markdown report for a human reviewer.

    The report summarizes already-computed safe aggregate evidence and candidate
    artifacts. It does not approve tests, infer official coverage, call an LLM,
    or expose raw source rows/failing values.
    """
    # Assemble the report from artifacts already produced in this run. Report
    # generation does not reread raw data, call the LLM, or recalculate checks.
    sections = [
        "# Data Test Suggestion Review Report",
        _review_boundary_section(),
        _run_summary_section(profile=profile, artifact_paths=artifact_paths),
        _dataset_profile_section(profile),
        _context_section(context=context, context_metadata=context_metadata),
        _candidate_source_section(
            payload=payload,
            llm_metadata=llm_metadata,
            candidate_validation_artifact=candidate_validation_artifact,
        ),
        _validation_section(
            candidate_validation_artifact=candidate_validation_artifact,
            rejected_suggestions_artifact=rejected_suggestions_artifact,
        ),
        _execution_section(execution_artifact),
        _reviewer_next_steps_section(),
    ]
    return "\n\n".join(section.rstrip() for section in sections) + "\n"


def _review_boundary_section() -> str:
    """Return fixed authority-boundary text for every report."""
    # These bullets are deliberately repeated in every report: validation and
    # execution can support review, but they must never become approval workflow.
    return "\n".join(
        [
            "## Review boundary",
            "- This report is for human review.",
            "- Candidate tests are not approved tests.",
            "- LLM-generated candidates, if present, are suggestions only.",
            "- Deterministic validation is a safety gate, not approval.",
            "- Execution results are aggregate check outcomes, not official test coverage.",
            "- No legal/compliance/privacy verdicts are made.",
            "- Raw rows, sampled records, source previews, top values, distinct values, raw failing rows, and failing values are not included.",
            "- Report generation is deterministic, local, and does not call an LLM.",
        ]
    )


def _run_summary_section(
    *, profile: DatasetProfile, artifact_paths: dict[str, str] | None
) -> str:
    """Return a run summary with local paths reduced to file names."""
    metadata = profile.dataset_metadata
    lines = [
        "## Run summary",
        f"- Agent name: {_cell(AGENT_NAME)}",
        f"- Package version: {_cell(__version__)}",
        f"- Input file name: {_cell(metadata.file_name)}",
        f"- Input file extension: {_cell(metadata.file_extension)}",
    ]
    if metadata.sheet_name:
        lines.append(f"- Sheet name: {_cell(metadata.sheet_name)}")
    lines.extend(
        [
            f"- Row count: {profile.row_count}",
            f"- Column count: {profile.column_count}",
            "- Artifact list:",
        ]
    )
    if artifact_paths:
        for artifact_name in sorted(artifact_paths):
            lines.append(
                f"  - {_cell(artifact_name)}: {_cell(_safe_file_name(artifact_paths[artifact_name]))}"
            )
    else:
        lines.append("  - No artifact paths were provided to the report generator.")
    return "\n".join(lines)


def _dataset_profile_section(profile: DatasetProfile) -> str:
    """Return readable aggregate-only profile evidence with no source examples."""
    # Use a compact overview plus type-specific detail sections so wide profile
    # evidence stays readable in Markdown.
    sections = [
        "## Dataset profile summary",
        f"- Row count: {profile.row_count}",
        f"- Column count: {profile.column_count}",
        "### Column overview",
        _markdown_table(
            ["column", "type", "nulls", "unique", "identifier hint", "low-cardinality hint"],
            [
                [
                    column.name,
                    column.profile_type,
                    _count_ratio(column.null_count, column.null_ratio),
                    _count_ratio(column.unique_count, column.unique_ratio),
                    column.likely_identifier_candidate,
                    column.low_cardinality_candidate,
                ]
                for column in profile.columns
            ],
        ),
    ]

    numeric_rows = [
        [column.name, column.numeric_min, column.numeric_max, column.numeric_mean]
        for column in profile.columns
        if column.profile_type == "numeric"
    ]
    if numeric_rows:
        sections.extend(
            [
                "### Numeric column details",
                _markdown_table(["column", "min", "max", "mean"], numeric_rows),
            ]
        )

    date_rows = [
        [
            column.name,
            column.parseable_date_count,
            column.parseable_date_ratio,
            column.min_date,
            column.max_date,
        ]
        for column in profile.columns
        if column.profile_type == "datetime"
    ]
    if date_rows:
        sections.extend(
            [
                "### Date-like column details",
                _markdown_table(
                    ["column", "parseable dates", "parseable ratio", "min date", "max date"],
                    date_rows,
                ),
            ]
        )

    text_rows = [
        [
            column.name,
            column.min_length,
            column.max_length,
            column.average_length,
            column.empty_string_count,
        ]
        for column in profile.columns
        if column.profile_type == "text"
    ]
    if text_rows:
        sections.extend(
            [
                "### Text column details",
                _markdown_table(
                    ["column", "min length", "max length", "average length", "empty strings"],
                    text_rows,
                ),
            ]
        )

    return "\n\n".join(sections)


def _context_section(
    *, context: DatasetContext | None, context_metadata: dict[str, Any] | None
) -> str:
    """Return human-authored context summary, if supplied."""
    lines = ["## Human-authored context summary"]
    if context is None:
        lines.append("- No context was provided.")
        return "\n".join(lines)

    missing_fields = []
    if context_metadata is not None:
        missing_fields = list(context_metadata.get("missing_context_fields", []))
    lines.extend(
        [
            f"- Dataset name: {_cell(context.dataset_name)}",
            f"- Expected grain: {_cell(context.expected_grain)}",
            f"- Preferred strictness: {_cell(context.preferred_strictness)}",
            f"- Important fields: {_cell(_join_list(context.important_fields))}",
            f"- Known ID fields: {_cell(_join_list(context.known_id_fields))}",
            f"- Known date fields: {_cell(_join_list(context.known_date_fields))}",
            f"- Known categorical fields: {_cell(_join_list(context.known_categorical_fields))}",
            f"- Fields to ignore: {_cell(_join_list(context.fields_to_ignore))}",
            f"- Business caveat count: {len(context.business_caveats)}",
            f"- Field note count: {len(context.field_notes)}",
            f"- Missing context fields: {_cell(_join_list(missing_fields))}",
        ]
    )
    if context.business_caveats:
        lines.append("- Business caveats:")
        for caveat in context.business_caveats:
            lines.append(f"  - {_cell(caveat)}")
    if context.field_notes:
        lines.append("- Field notes:")
        for field_name in sorted(context.field_notes):
            lines.append(f"  - {_cell(field_name)}: {_cell(context.field_notes[field_name])}")
    return "\n".join(lines)


def _candidate_source_section(
    *,
    payload: dict[str, Any],
    llm_metadata: dict[str, Any] | None,
    candidate_validation_artifact: dict[str, Any] | None,
) -> str:
    """Return candidate provenance without prompts or LLM raw responses."""
    lines = ["## Candidate source summary"]
    if llm_metadata is not None:
        # Provenance is enough for review here; prompts, raw responses,
        # chain-of-thought, and API keys are intentionally excluded.
        lines.extend(
            [
                "- Candidate source: LLM-generated candidates used.",
                f"- Model name: {_cell(llm_metadata.get('model'))}",
                f"- Max candidates: {_cell(llm_metadata.get('max_candidates'))}",
                f"- Generated candidate count: {_cell(llm_metadata.get('generated_candidate_count'))}",
                "- raw_rows_sent_to_llm = false",
                "- Generated candidates are not approved tests.",
                "- Raw prompts, raw OpenAI responses, chain-of-thought, and API keys are not included.",
            ]
        )
        return "\n".join(lines)

    if candidate_validation_artifact is not None:
        generated = candidate_validation_artifact.get("candidate_tests_generated_by_this_agent")
        source = "LLM-generated candidates used." if generated else "Manual candidate file used."
        lines.append(f"- Candidate source: {source}")
        lines.append(
            f"- llm_called = {_bool_text(candidate_validation_artifact.get('llm_called'))}"
        )
        lines.append("- Candidate tests are not approved tests.")
        return "\n".join(lines)

    boundary = payload.get("authority_boundary", {}) if isinstance(payload, dict) else {}
    lines.extend(
        [
            "- No candidate generation or validation was requested.",
            f"- llm_called = {_bool_text(boundary.get('llm_called', False))}",
            "- Candidate tests are not approved tests because no candidates were accepted or promoted by this run.",
        ]
    )
    return "\n".join(lines)


def _validation_section(
    *,
    candidate_validation_artifact: dict[str, Any] | None,
    rejected_suggestions_artifact: dict[str, Any] | None,
) -> str:
    """Return validation summary tables, if validation ran."""
    lines = ["## Validation summary"]
    if candidate_validation_artifact is None:
        lines.append("- Candidate validation was not requested.")
        return "\n".join(lines)

    summary = candidate_validation_artifact.get("summary", {})
    lines.extend(
        [
            f"- Input candidate count: {_cell(summary.get('input_candidate_count'))}",
            f"- Validated count: {_cell(summary.get('validated_count'))}",
            f"- Rejected count: {_cell(summary.get('rejected_count'))}",
            "- Deterministic validation is a safety gate, not approval.",
            "### Validated candidates",
            _markdown_table(
                ["test_id", "type", "column", "severity", "source", "notes"],
                [
                    [
                        candidate.get("test_id"),
                        candidate.get("test_type"),
                        candidate.get("column"),
                        candidate.get("severity"),
                        candidate.get("suggested_by"),
                        _join_list(candidate.get("validation_notes", [])),
                    ]
                    for candidate in candidate_validation_artifact.get("validated_candidates", [])
                ],
            ),
        ]
    )
    # Rejection reason codes are sufficient for review and avoid dumping full
    # candidate payloads into the Markdown report.
    rejected_candidates: Iterable[dict[str, Any]] = []
    if rejected_suggestions_artifact is not None:
        rejected_candidates = rejected_suggestions_artifact.get("rejected_candidates", [])
    lines.extend(
        [
            "### Rejected candidates",
            _markdown_table(
                ["index", "test_id", "type", "column", "reason codes"],
                [
                    [
                        candidate.get("candidate_index"),
                        candidate.get("test_id"),
                        candidate.get("test_type"),
                        candidate.get("column"),
                        _join_list(
                            reason.get("reason_code")
                            for reason in candidate.get("rejection_reasons", [])
                        ),
                    ]
                    for candidate in rejected_candidates
                ],
            ),
        ]
    )
    return "\n".join(lines).replace("\n###", "\n\n###")


def _execution_section(execution_artifact: dict[str, Any] | None) -> str:
    """Return aggregate-only execution summary, if execution ran."""
    lines = ["## Execution summary"]
    if execution_artifact is None:
        lines.append("- Candidate execution was not requested.")
        return "\n".join(lines)

    summary = execution_artifact.get("summary", {})
    # Execution metrics are aggregate-only; reports should never include raw
    # failing rows or unexpected values.
    lines.extend(
        [
            f"- Executed count: {_cell(summary.get('executed_count'))}",
            f"- Passed count: {_cell(summary.get('passed_count'))}",
            f"- Failed count: {_cell(summary.get('failed_count'))}",
            "- Execution is local-only.",
            "- Failed checks are review outcomes, not CLI/process failures.",
            "- Execution results are aggregate check outcomes, not official test coverage.",
            _markdown_table(
                ["test_id", "type", "column", "status", "failures", "failure ratio", "key metrics"],
                [
                    [
                        result.get("test_id"),
                        result.get("test_type"),
                        result.get("column"),
                        result.get("status"),
                        result.get("failure_count"),
                        result.get("failure_ratio"),
                        _format_metrics(result.get("metrics", {})),
                    ]
                    for result in execution_artifact.get("execution_results", [])
                ],
            ),
        ]
    )
    return "\n".join(lines)


def _reviewer_next_steps_section() -> str:
    """Return cautious next steps that preserve human authority."""
    return "\n".join(
        [
            "## Suggested reviewer next steps",
            "- Review the candidate tests and rationales.",
            "- Check whether rejected candidates reveal useful intent or bad assumptions.",
            "- Review failed execution results before deciding whether a candidate should become official.",
            "- Decide manually which tests, if any, should be promoted into a real test suite outside this agent.",
        ]
    )


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Return a simple deterministic Markdown table."""
    safe_headers = [_cell(header) for header in headers]
    lines = [
        "| " + " | ".join(safe_headers) + " |",
        "| " + " | ".join("---" for _ in safe_headers) + " |",
    ]
    if not rows:
        lines.append("| " + " | ".join("not present" for _ in safe_headers) + " |")
        return "\n".join(lines)
    for row in rows:
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    """Return a sanitized Markdown table/list value."""
    if value is None or value == "":
        text = "not provided"
    elif isinstance(value, bool):
        text = _bool_text(value)
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _bool_text(value: Any) -> str:
    """Format booleans as lowercase deterministic text."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return _cell(value)


def _safe_file_name(path_value: str) -> str:
    """Return only a file name so reports avoid absolute local paths."""
    return Path(str(path_value)).name


def _join_list(values: Iterable[Any] | None) -> str:
    """Join values deterministically for compact report cells."""
    if values is None:
        return "none"
    rendered = [_cell(value) for value in values if value is not None]
    if not rendered:
        return "none"
    return ", ".join(rendered)


def _count_ratio(count: Any, ratio: Any) -> str:
    """Format an aggregate count and ratio compactly for overview tables."""
    return f"{_cell(count)} ({_cell(ratio)})"


def _format_metrics(metrics: dict[str, Any]) -> str:
    """Format aggregate execution metrics without row-level values."""
    if not isinstance(metrics, dict) or not metrics:
        return "none"
    return "; ".join(f"{_cell(key)}={_cell(metrics[key])}" for key in sorted(metrics))
