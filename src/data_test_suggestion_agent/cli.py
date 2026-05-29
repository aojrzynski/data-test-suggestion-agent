"""Command-line interface for local dataset intake and safe profiling.

PR #2 adds deterministic CSV/XLSX/XLSM intake and aggregate-only profiling. It
still does not load YAML context, call an LLM, generate candidate tests,
validate suggestions, execute tests, or write reports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.intake import IntakeError, load_dataset
from data_test_suggestion_agent.output_writers import PROFILE_FILE_NAME, TRACE_FILE_NAME, write_json_artifact
from data_test_suggestion_agent.profiling import profile_dataset

AGENT_NAME = "data-test-suggestion-agent"
PACKAGE_NAME = "data_test_suggestion_agent"

FUTURE_STAGES = (
    "dataset_intake",
    "profiling",
    "context_loading",
    "evidence_payload",
    "llm_suggestions",
    "suggestion_validation",
    "test_execution",
    "reporting",
)

NOT_IMPLEMENTED_STAGES = (
    "context_loading",
    "evidence_payload",
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
            "Test suggestion logic and LLM calls are not implemented yet."
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
    return {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": "scaffold_completed",
        "message": (
            "Scaffold run completed. Provide --input to run deterministic dataset "
            "intake and safe profiling. Test suggestion logic is not implemented yet."
        ),
        "artifact_paths": {"trace": TRACE_FILE_NAME},
        "stages": stages,
    }


def build_profile_trace(
    *,
    metadata: dict[str, object],
    trace_path: Path,
    profile_path: Path,
) -> dict[str, object]:
    """Return a trace payload for a completed intake/profile run."""
    stages = {stage: "not_implemented" for stage in NOT_IMPLEMENTED_STAGES}
    stages["dataset_intake"] = "completed"
    stages["profiling"] = "completed"
    return {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": "profiling_completed",
        "message": (
            "Dataset intake and safe aggregate profiling completed. No test "
            "suggestions were generated."
        ),
        "dataset_metadata": metadata,
        "artifact_paths": {
            "trace": str(trace_path),
            "dataset_profile": str(profile_path),
        },
        "stages": stages,
    }


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
        trace_path = write_scaffold_trace(output_dir)
        print(f"Scaffold run completed. Trace written to {trace_path}.")
        return 0

    try:
        ingested = load_dataset(args.input, sheet_name=args.sheet)
        profile = profile_dataset(ingested.dataframe, ingested.metadata)
    except IntakeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    profile_path = write_json_artifact(output_dir, PROFILE_FILE_NAME, profile.to_dict())
    trace_path = output_dir / TRACE_FILE_NAME
    trace = build_profile_trace(
        metadata=ingested.metadata.to_dict(),
        trace_path=trace_path,
        profile_path=profile_path,
    )
    write_json_artifact(output_dir, TRACE_FILE_NAME, trace)

    print(
        "Dataset intake and safe profiling completed. "
        f"Trace written to {trace_path}. Profile written to {profile_path}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
