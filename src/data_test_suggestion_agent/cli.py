"""Command-line interface for local profiling, candidate workflows, execution, and reporting."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.candidate_loader import (
    CandidateLoadError,
    load_candidate_tests,
)
from data_test_suggestion_agent.candidate_validator import (
    build_rejected_suggestions_artifact,
    build_validated_suggestions_artifact,
    validate_candidate_tests,
)
from data_test_suggestion_agent.context_loader import (
    ContextLoadError,
    load_context,
    summarize_context,
)
from data_test_suggestion_agent.evidence_payload import build_test_suggestion_payload
from data_test_suggestion_agent.intake import IntakeError, load_dataset
from data_test_suggestion_agent.llm_candidate_generator import (
    CandidateGenerationError,
    build_llm_candidate_tests_artifact,
    generate_candidate_tests_with_openai,
)
from data_test_suggestion_agent.test_executor import (
    build_test_execution_results_artifact,
    execute_validated_candidates,
)
from data_test_suggestion_agent.output_writers import (
    LLM_CANDIDATE_TESTS_FILE_NAME,
    PAYLOAD_FILE_NAME,
    PROFILE_FILE_NAME,
    REPORT_FILE_NAME,
    REJECTED_SUGGESTIONS_FILE_NAME,
    TEST_EXECUTION_RESULTS_FILE_NAME,
    VALIDATED_SUGGESTIONS_FILE_NAME,
    TRACE_FILE_NAME,
    write_json_artifact,
    write_text_artifact,
)
from data_test_suggestion_agent.profiling import profile_dataset
from data_test_suggestion_agent.report_generator import build_review_report

AGENT_NAME = "data-test-suggestion-agent"
PACKAGE_NAME = "data_test_suggestion_agent"

FUTURE_STAGES = (
    "dataset_intake",
    "profiling",
    "context_loading",
    "evidence_payload",
    "candidate_loading",
    "llm_suggestions",
    "suggestion_validation",
    "test_execution",
    "reporting",
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog=AGENT_NAME,
        description=(
            "Profile a local CSV/XLSX/XLSM dataset into safe aggregate evidence. "
            "Optionally validate manual candidates, generate bounded LLM candidates "
            "from safe evidence only, execute validated candidates locally, and "
            "optionally write a deterministic human review report."
        ),
    )
    parser.add_argument(
        "--input",
        help="Path to a CSV, XLSX, or XLSM dataset to profile.",
    )
    parser.add_argument(
        "--sheet",
        help="Excel sheet name to load. Only valid for .xlsx and .xlsm inputs.",
    )
    parser.add_argument(
        "--context",
        help="Path to an optional human-authored YAML dataset context file.",
    )
    parser.add_argument(
        "--candidates",
        help="Path to an optional local JSON file of manually supplied candidate tests.",
    )
    parser.add_argument(
        "--generate-candidates",
        action="store_true",
        help="Call an optional OpenAI LLM to generate structured candidate tests from safe evidence only.",
    )
    parser.add_argument(
        "--llm-model",
        help="OpenAI model name for --generate-candidates. Defaults to DATA_TEST_AGENT_LLM_MODEL.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=8,
        help="Maximum candidate suggestions to request from the LLM when --generate-candidates is used.",
    )
    parser.add_argument(
        "--execute-candidates",
        action="store_true",
        help="Execute locally validated candidate tests with deterministic aggregate-only logic.",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write a deterministic local Markdown report for human review only.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where JSON artifacts will be written.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{AGENT_NAME} {__version__}",
    )
    return parser


def build_scaffold_trace() -> dict[str, object]:
    """Return the deterministic no-input scaffold trace payload."""
    stages = {stage: "not_implemented" for stage in FUTURE_STAGES}
    stages["dataset_intake"] = "not_requested"
    stages["profiling"] = "not_requested"
    stages["context_loading"] = "not_requested"
    stages["candidate_loading"] = "not_requested"
    stages["suggestion_validation"] = "not_requested"
    stages["test_execution"] = "not_requested"
    stages["reporting"] = "not_requested"
    return {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": "scaffold_completed",
        "message": (
            "Scaffold run completed. Provide --input to run deterministic dataset "
            "intake and safe profiling. Candidate generation is optional and "
            "bounded; candidate execution is opt-in after validation."
        ),
        "artifact_paths": {"trace": TRACE_FILE_NAME},
        "stages": stages,
    }


def build_profile_trace(
    *,
    metadata: dict[str, object],
    trace_path: Path,
    profile_path: Path,
    payload_path: Path,
    context_metadata: dict[str, object] | None = None,
    candidate_metadata: dict[str, object] | None = None,
    execution_metadata: dict[str, object] | None = None,
    llm_metadata: dict[str, object] | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Return a trace payload for a completed intake/profile run."""
    stages = {stage: "not_implemented" for stage in FUTURE_STAGES}
    stages["dataset_intake"] = "completed"
    stages["profiling"] = "completed"
    stages["context_loading"] = (
        "completed" if context_metadata is not None else "not_requested"
    )
    stages["evidence_payload"] = "completed"
    stages["llm_suggestions"] = "completed" if llm_metadata is not None else "not_requested"
    stages["candidate_loading"] = (
        "not_applicable"
        if llm_metadata is not None
        else "completed" if candidate_metadata is not None else "not_requested"
    )
    stages["suggestion_validation"] = (
        "completed" if candidate_metadata is not None else "not_requested"
    )
    stages["test_execution"] = (
        "completed" if execution_metadata is not None else "not_requested"
    )
    stages["reporting"] = "completed" if report_path is not None else "not_requested"

    if execution_metadata is not None:
        run_status = "test_execution_completed"
        message = "Deterministic execution completed for validated candidates."
    elif llm_metadata is not None:
        run_status = "llm_candidate_generation_completed"
        message = "LLM candidate generation completed, followed by deterministic validation."
    elif candidate_metadata is not None:
        run_status = "candidate_validation_completed"
        message = "Manual candidate validation completed; no LLM generation."
    else:
        run_status = "evidence_payload_completed"
        message = (
            "Evidence payload construction completed; no test suggestions generated "
            "unless manual or LLM candidate generation is requested."
        )

    # Context can inform later review workflows, but it is not a test suggestion
    # and is intentionally kept out of dataset_profile.json.
    trace: dict[str, object] = {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": run_status,
        "message": (
            f"{message} Human review report was written."
            if report_path is not None
            else message
        ),
        "dataset_metadata": metadata,
        "artifact_paths": {
            "trace": str(trace_path),
            "dataset_profile": str(profile_path),
            "test_suggestion_payload": str(payload_path),
        },
        "stages": stages,
    }
    if context_metadata is not None:
        trace["context_metadata"] = context_metadata
    if llm_metadata is not None:
        trace["llm_generation"] = llm_metadata
        artifact_paths = trace["artifact_paths"]
        if isinstance(artifact_paths, dict):
            artifact_paths["llm_candidate_tests"] = llm_metadata[
                "llm_candidate_tests_path"
            ]
    if candidate_metadata is not None:
        trace["candidate_validation"] = candidate_metadata
        artifact_paths = trace["artifact_paths"]
        if isinstance(artifact_paths, dict):
            artifact_paths["validated_test_suggestions"] = candidate_metadata[
                "validated_test_suggestions_path"
            ]
            artifact_paths["rejected_test_suggestions"] = candidate_metadata[
                "rejected_test_suggestions_path"
            ]
    if execution_metadata is not None:
        trace["test_execution"] = execution_metadata
        artifact_paths = trace["artifact_paths"]
        if isinstance(artifact_paths, dict):
            artifact_paths["test_execution_results"] = execution_metadata[
                "test_execution_results_path"
            ]
    if report_path is not None:
        artifact_paths = trace["artifact_paths"]
        if isinstance(artifact_paths, dict):
            artifact_paths["test_suggestion_report"] = str(report_path)
    return trace


def build_trace() -> dict[str, object]:
    """Return the deterministic no-input scaffold trace payload.

    This compatibility wrapper keeps the PR #1 scaffold helper available while
    the CLI grows dataset intake and profiling behavior.
    """
    return build_scaffold_trace()


def write_scaffold_trace(output_dir: Path) -> Path:
    """Create the output directory, write the scaffold trace, and return its path."""
    return write_json_artifact(output_dir, TRACE_FILE_NAME, build_scaffold_trace())


def write_trace(output_dir: Path) -> Path:
    """Write the no-input scaffold trace and return its path.

    This compatibility wrapper preserves the original scaffold API name.
    """
    return write_scaffold_trace(output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)

    if args.generate_candidates and args.max_candidates < 1:
        print("Error: --max-candidates must be at least 1.", file=sys.stderr)
        return 2

    if args.generate_candidates and args.candidates is not None:
        print(
            "Error: use either --candidates for manual candidate input or --generate-candidates for LLM generation, not both.",
            file=sys.stderr,
        )
        return 2

    if args.input is None:
        if args.sheet is not None:
            print(
                "Error: --sheet requires --input and is only valid for Excel inputs.",
                file=sys.stderr,
            )
            return 2
        if args.context is not None:
            print(
                "Error: --context requires --input so context can be checked against dataset columns.",
                file=sys.stderr,
            )
            return 2
        if args.candidates is not None:
            print(
                "Error: --candidates requires --input so candidates can be validated against dataset columns.",
                file=sys.stderr,
            )
            return 2
        if args.generate_candidates:
            print(
                "Error: --generate-candidates requires --input so only safe evidence from a loaded dataset is sent to the LLM.",
                file=sys.stderr,
            )
            return 2
        if args.execute_candidates:
            print(
                "Error: --execute-candidates requires --input and candidate validation so validated candidates can be executed locally.",
                file=sys.stderr,
            )
            return 2
        if args.write_report:
            print(
                "Error: --write-report requires --input so a deterministic human review report can summarize a completed dataset run.",
                file=sys.stderr,
            )
            return 2
        trace_path = write_scaffold_trace(output_dir)
        print(f"Scaffold run completed. Trace written to {trace_path}.")
        return 0

    if args.execute_candidates and args.candidates is None and not args.generate_candidates:
        print(
            "Error: --execute-candidates requires --candidates or --generate-candidates so only validated candidate tests can be executed.",
            file=sys.stderr,
        )
        return 2

    resolved_model = None
    if args.generate_candidates:
        resolved_model = args.llm_model or os.environ.get("DATA_TEST_AGENT_LLM_MODEL")
        if not resolved_model:
            print(
                "Error: --generate-candidates requires --llm-model or DATA_TEST_AGENT_LLM_MODEL.",
                file=sys.stderr,
            )
            return 2
        if not os.environ.get("OPENAI_API_KEY"):
            print(
                "Error: OPENAI_API_KEY is required when --generate-candidates is used.",
                file=sys.stderr,
            )
            return 2

    try:
        ingested = load_dataset(args.input, sheet_name=args.sheet)
        profile = profile_dataset(ingested.dataframe, ingested.metadata)
        context = None
        context_metadata = None
        if args.context is not None:
            context = load_context(args.context)
            context_metadata = summarize_context(
                context=context,
                context_path=args.context,
                dataset_columns=ingested.metadata.columns,
            )
        candidate_entries = None
        validation_result = None
        if args.candidates is not None:
            candidate_entries = load_candidate_tests(args.candidates)
            validation_result = validate_candidate_tests(
                candidate_entries=candidate_entries,
                profile=profile,
                context=context,
            )
    except (IntakeError, ContextLoadError, CandidateLoadError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    profile_path = write_json_artifact(output_dir, PROFILE_FILE_NAME, profile.to_dict())
    payload = build_test_suggestion_payload(
        profile=profile,
        context=context,
        context_metadata=context_metadata,
    )
    payload_path = write_json_artifact(output_dir, PAYLOAD_FILE_NAME, payload)

    llm_metadata = None
    if args.generate_candidates:
        assert resolved_model is not None
        try:
            # The LLM receives only the safe evidence payload. Its structured
            # output is not trusted; deterministic validation below remains the
            # authoritative gate before any optional local execution.
            candidate_entries = generate_candidate_tests_with_openai(
                test_suggestion_payload=payload,
                model=resolved_model,
                max_candidates=args.max_candidates,
            )
        except CandidateGenerationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        llm_candidate_artifact = build_llm_candidate_tests_artifact(
            candidate_tests=candidate_entries,
            source_payload_artifact=str(payload_path),
            model=resolved_model,
            max_candidates=args.max_candidates,
        )
        llm_candidate_path = write_json_artifact(
            output_dir,
            LLM_CANDIDATE_TESTS_FILE_NAME,
            llm_candidate_artifact,
        )
        validation_result = validate_candidate_tests(
            candidate_entries=candidate_entries,
            profile=profile,
            context=context,
        )
        llm_metadata = {
            "candidate_source": "llm_generation",
            "model": resolved_model,
            "max_candidates": args.max_candidates,
            "generated_candidate_count": len(candidate_entries),
            "llm_candidate_tests_path": str(llm_candidate_path),
            "llm_called": True,
            "raw_rows_sent_to_llm": False,
        }

    candidate_metadata = None
    execution_metadata = None
    validated_suggestions_artifact = None
    rejected_suggestions_artifact = None
    execution_artifact = None
    generated_by_agent = bool(args.generate_candidates)
    llm_called = bool(args.generate_candidates)
    if validation_result is not None:
        validated_suggestions_artifact = build_validated_suggestions_artifact(
            validation_result,
            candidate_tests_generated_by_this_agent=generated_by_agent,
            llm_called=llm_called,
        )
        rejected_suggestions_artifact = build_rejected_suggestions_artifact(
            validation_result,
            candidate_tests_generated_by_this_agent=generated_by_agent,
            llm_called=llm_called,
        )
        validated_path = write_json_artifact(
            output_dir,
            VALIDATED_SUGGESTIONS_FILE_NAME,
            validated_suggestions_artifact,
        )
        rejected_path = write_json_artifact(
            output_dir,
            REJECTED_SUGGESTIONS_FILE_NAME,
            rejected_suggestions_artifact,
        )
        if args.generate_candidates:
            candidate_metadata = {
                "candidate_source": "llm_generation",
                "llm_called": True,
                "raw_rows_sent_to_llm": False,
                "model": resolved_model,
                "max_candidates": args.max_candidates,
                "input_candidate_count": validation_result.input_candidate_count,
                "generated_candidate_count": validation_result.input_candidate_count,
                "validated_candidate_count": validation_result.validated_count,
                "rejected_candidate_count": validation_result.rejected_count,
                "validated_test_suggestions_path": str(validated_path),
                "rejected_test_suggestions_path": str(rejected_path),
            }
            if llm_metadata is not None:
                llm_metadata["validated_candidate_count"] = validation_result.validated_count
                llm_metadata["rejected_candidate_count"] = validation_result.rejected_count
        else:
            candidate_metadata = {
                "candidate_source": "manual_file",
                "llm_called": False,
                "candidates_path": str(args.candidates),
                "candidates_file_name": Path(args.candidates).name,
                "input_candidate_count": validation_result.input_candidate_count,
                "validated_candidate_count": validation_result.validated_count,
                "rejected_candidate_count": validation_result.rejected_count,
                "validated_test_suggestions_path": str(validated_path),
                "rejected_test_suggestions_path": str(rejected_path),
            }

        if args.execute_candidates:
            # Execution is opt-in and runs only candidates that passed validation.
            # Failed check results are aggregate data-quality outcomes, not CLI
            # failures and not approvals of these suggestions.
            execution_results = execute_validated_candidates(
                dataframe=ingested.dataframe,
                validated_candidates=validation_result.validated_candidates,
            )
            execution_artifact = build_test_execution_results_artifact(
                validated_candidate_count=validation_result.validated_count,
                execution_results=execution_results,
                candidate_tests_generated_by_this_agent=generated_by_agent,
                llm_called=llm_called,
            )
            execution_path = write_json_artifact(
                output_dir,
                TEST_EXECUTION_RESULTS_FILE_NAME,
                execution_artifact,
            )
            execution_summary = execution_artifact["summary"]
            execution_metadata = {
                "executed_candidate_count": execution_summary["executed_count"],
                "passed_candidate_count": execution_summary["passed_count"],
                "failed_candidate_count": execution_summary["failed_count"],
                "test_execution_results_path": str(execution_path),
            }

    report_path = None
    if args.write_report:
        report_path = output_dir / REPORT_FILE_NAME
        artifact_paths = {
            "trace": str(output_dir / TRACE_FILE_NAME),
            "dataset_profile": str(profile_path),
            "test_suggestion_payload": str(payload_path),
        }
        if llm_metadata is not None:
            artifact_paths["llm_candidate_tests"] = str(output_dir / LLM_CANDIDATE_TESTS_FILE_NAME)
        if validated_suggestions_artifact is not None:
            artifact_paths["validated_test_suggestions"] = str(output_dir / VALIDATED_SUGGESTIONS_FILE_NAME)
            artifact_paths["rejected_test_suggestions"] = str(output_dir / REJECTED_SUGGESTIONS_FILE_NAME)
        if execution_artifact is not None:
            artifact_paths["test_execution_results"] = str(output_dir / TEST_EXECUTION_RESULTS_FILE_NAME)
        artifact_paths["test_suggestion_report"] = str(report_path)
        report = build_review_report(
            profile=profile,
            payload=payload,
            context=context,
            context_metadata=context_metadata,
            llm_metadata=llm_metadata,
            candidate_validation_artifact=validated_suggestions_artifact,
            rejected_suggestions_artifact=rejected_suggestions_artifact,
            execution_artifact=execution_artifact,
            artifact_paths=artifact_paths,
        )
        # The report is generated after all prior stages succeed so clean
        # failure paths never leave a partial review artifact behind.
        write_text_artifact(output_dir, REPORT_FILE_NAME, report)

    trace_path = output_dir / TRACE_FILE_NAME
    trace = build_profile_trace(
        metadata=ingested.metadata.to_dict(),
        trace_path=trace_path,
        profile_path=profile_path,
        payload_path=payload_path,
        context_metadata=context_metadata,
        candidate_metadata=candidate_metadata,
        execution_metadata=execution_metadata,
        llm_metadata=llm_metadata,
        report_path=report_path,
    )
    write_json_artifact(output_dir, TRACE_FILE_NAME, trace)

    print(
        "Dataset intake, safe profiling, and evidence payload construction completed. "
        f"Trace written to {trace_path}. Profile written to {profile_path}. "
        f"Payload written to {payload_path}."
        + (f" Report written to {report_path}." if report_path is not None else "")
    )
    return 0
