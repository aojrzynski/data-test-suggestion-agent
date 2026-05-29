"""Command-line scaffold for the Data Test Suggestion Agent.

This PR intentionally provides only a runnable package and trace-writing CLI.
It does not perform dataset intake, profiling, test suggestion, validation, or
execution. Future LLM-assisted behavior is expected to be bounded by
human-reviewable candidate generation and deterministic validation steps.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from data_test_suggestion_agent import __version__

AGENT_NAME = "data-test-suggestion-agent"
PACKAGE_NAME = "data_test_suggestion_agent"
TRACE_FILE_NAME = "data_test_trace.json"

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


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog=AGENT_NAME,
        description=(
            "Write a scaffold trace for the Data Test Suggestion Agent. "
            "Dataset analysis and test suggestion logic are not implemented yet."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where the scaffold trace JSON file will be written.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{AGENT_NAME} {__version__}",
    )
    return parser


def build_trace() -> dict[str, object]:
    """Return the deterministic scaffold trace payload."""
    return {
        "agent_name": AGENT_NAME,
        "package_name": PACKAGE_NAME,
        "package_version": __version__,
        "run_status": "scaffold_completed",
        "message": (
            "Scaffold run completed. Dataset intake and test suggestion logic "
            "are not implemented yet."
        ),
        "stages": {stage: "not_implemented" for stage in FUTURE_STAGES},
    }


def write_trace(output_dir: Path) -> Path:
    """Create the output directory, write the scaffold trace, and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / TRACE_FILE_NAME
    trace_path.write_text(
        json.dumps(build_trace(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return trace_path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scaffold CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    trace_path = write_trace(Path(args.output_dir))
    print(f"Scaffold run completed. Trace written to {trace_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
