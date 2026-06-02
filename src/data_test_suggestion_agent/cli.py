"""Command-line interface for local intake, profiling, context, and payloads.

PR #4 adds deterministic safe evidence payload construction. The CLI still does
not call an LLM, generate candidate tests, execute tests, or write reports.
It can validate manually supplied candidate suggestions against a strict local
contract.
"""

from __future__ import annotations

import argparse
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
from data_test_suggestion_agent.output_writers import (
    PAYLOAD_FILE_NAME,
    PROFILE_FILE_NAME,
    REJECTED_SUGGESTIONS_FILE_NAME,
    VALIDATED_SUGGESTIONS_FILE_NAME,
    TRACE_FILE_NAME,
    write_json_artifact,
)
from data_test_suggestion_agent.profiling import profile_dataset

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
            "Optionally validate manual candidate suggestions; LLM calls and "
            "test execution are not implemented yet."
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
    return {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": "scaffold_completed",
        "message": (
            "Scaffold run completed. Provide --input to run deterministic dataset "
            "intake and safe profiling. Candidate generation, LLM calls, and "
            "test execution are not implemented yet."
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
) -> dict[str, object]:
    """Return a trace payload for a completed intake/profile run."""
    stages = {stage: "not_implemented" for stage in FUTURE_STAGES}
    stages["dataset_intake"] = "completed"
    stages["profiling"] = "completed"
    stages["context_loading"] = (
        "completed" if context_metadata is not None else "not_requested"
    )
    stages["evidence_payload"] = "completed"
    stages["candidate_loading"] = (
        "completed" if candidate_metadata is not None else "not_requested"
    )
    stages["suggestion_validation"] = (
        "completed" if candidate_metadata is not None else "not_requested"
    )

    # Context can inform later review workflows, but it is not a test suggestion
    # and is intentionally kept out of dataset_profile.json.
    trace: dict[str, object] = {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": "evidence_payload_completed",
        "message": (
            "Dataset intake, safe aggregate profiling, and local evidence payload "
            "construction completed. No test suggestions were generated."
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
        trace_path = write_scaffold_trace(output_dir)
        print(f"Scaffold run completed. Trace written to {trace_path}.")
        return 0

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

    candidate_metadata = None
    if validation_result is not None:
        validated_path = write_json_artifact(
            output_dir,
            VALIDATED_SUGGESTIONS_FILE_NAME,
            build_validated_suggestions_artifact(validation_result),
        )
        rejected_path = write_json_artifact(
            output_dir,
            REJECTED_SUGGESTIONS_FILE_NAME,
            build_rejected_suggestions_artifact(validation_result),
        )
        candidate_metadata = {
            "candidates_path": str(args.candidates),
            "candidates_file_name": Path(args.candidates).name,
            "input_candidate_count": validation_result.input_candidate_count,
            "validated_candidate_count": validation_result.validated_count,
            "rejected_candidate_count": validation_result.rejected_count,
            "validated_test_suggestions_path": str(validated_path),
            "rejected_test_suggestions_path": str(rejected_path),
        }

    trace_path = output_dir / TRACE_FILE_NAME
    trace = build_profile_trace(
        metadata=ingested.metadata.to_dict(),
        trace_path=trace_path,
        profile_path=profile_path,
        payload_path=payload_path,
        context_metadata=context_metadata,
        candidate_metadata=candidate_metadata,
    )
    write_json_artifact(output_dir, TRACE_FILE_NAME, trace)

    print(
        "Dataset intake, safe profiling, and evidence payload construction completed. "
        f"Trace written to {trace_path}. Profile written to {profile_path}. "
        f"Payload written to {payload_path}."
    )
    if validation_result is not None:
        print(
            "Candidate validation completed. "
            f"Validated {validation_result.validated_count} candidate(s) and "
            f"rejected {validation_result.rejected_count} candidate(s)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
