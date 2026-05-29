"""Tests for the Data Test Suggestion Agent CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.cli import FUTURE_STAGES, main
from data_test_suggestion_agent.output_writers import PROFILE_FILE_NAME, TRACE_FILE_NAME

SAMPLE_DATASET = Path("sample_data/customers/customers_for_test_suggestions.csv")
SAMPLE_CONTEXT = Path("config/examples/customer_dataset_context.yaml")


def test_cli_writes_scaffold_trace_without_profile(tmp_path, capsys):
    """No-input mode should keep scaffold behavior and avoid profile output."""
    output_dir = tmp_path / "outputs"

    exit_code = main(["--output-dir", str(output_dir)])

    trace_path = output_dir / TRACE_FILE_NAME
    assert exit_code == 0
    assert output_dir.is_dir()
    assert trace_path.is_file()
    assert not (output_dir / PROFILE_FILE_NAME).exists()
    assert str(trace_path) in capsys.readouterr().out

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["run_status"] == "scaffold_completed"
    assert trace["message"].startswith("Scaffold run completed")
    assert trace["package_version"] == __version__
    assert set(trace["stages"]) == set(FUTURE_STAGES)
    assert trace["stages"]["dataset_intake"] == "not_requested"
    assert trace["stages"]["profiling"] == "not_requested"
    assert trace["stages"]["context_loading"] == "not_requested"


def test_cli_input_mode_writes_trace_and_profile(tmp_path, capsys):
    """Input mode should write both JSON artifacts and completed stages."""
    output_dir = tmp_path / "outputs"

    exit_code = main(["--input", str(SAMPLE_DATASET), "--output-dir", str(output_dir)])

    trace_path = output_dir / TRACE_FILE_NAME
    profile_path = output_dir / PROFILE_FILE_NAME
    assert exit_code == 0
    assert trace_path.is_file()
    assert profile_path.is_file()
    output = capsys.readouterr().out
    assert str(trace_path) in output
    assert str(profile_path) in output

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["run_status"] == "profiling_completed"
    assert trace["stages"]["dataset_intake"] == "completed"
    assert trace["stages"]["profiling"] == "completed"
    assert trace["stages"]["context_loading"] == "not_requested"
    assert trace["stages"]["llm_suggestions"] == "not_implemented"
    assert "context_metadata" not in trace
    assert trace["dataset_metadata"]["file_name"] == "customers_for_test_suggestions.csv"
    assert trace["dataset_metadata"]["row_count"] == 24
    assert trace["artifact_paths"]["dataset_profile"] == str(profile_path)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["row_count"] == 24
    assert profile["column_count"] == 9
    assert "alex.rivera@example.com" not in profile_path.read_text(encoding="utf-8")


def test_cli_input_with_context_writes_trace_metadata_and_profile(tmp_path, capsys):
    """Input plus context mode should record context metadata in trace only."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(SAMPLE_CONTEXT),
            "--output-dir",
            str(output_dir),
        ]
    )

    trace_path = output_dir / TRACE_FILE_NAME
    profile_path = output_dir / PROFILE_FILE_NAME
    assert exit_code == 0
    assert trace_path.is_file()
    assert profile_path.is_file()
    assert str(trace_path) in capsys.readouterr().out

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["stages"]["dataset_intake"] == "completed"
    assert trace["stages"]["profiling"] == "completed"
    assert trace["stages"]["context_loading"] == "completed"
    assert trace["stages"]["evidence_payload"] == "not_implemented"
    assert trace["stages"]["llm_suggestions"] == "not_implemented"
    context_metadata = trace["context_metadata"]
    assert context_metadata["context_path"] == str(SAMPLE_CONTEXT)
    assert context_metadata["context_file_name"] == SAMPLE_CONTEXT.name
    assert context_metadata["context_loading"] == "completed"
    assert context_metadata["dataset_name"] == "synthetic_customer_dataset"
    assert context_metadata["preferred_strictness"] == "standard"
    assert context_metadata["referenced_field_count"] == 8
    assert context_metadata["missing_context_fields"] == []
    assert context_metadata["context_warning_count"] == 0

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["row_count"] == 24
    assert "context_metadata" not in profile
    assert "preferred_strictness" not in profile


def test_context_loading_does_not_modify_dataset_profile(tmp_path):
    """Context metadata should not be copied into deterministic profile output."""
    without_context = tmp_path / "without_context"
    with_context = tmp_path / "with_context"

    assert main(["--input", str(SAMPLE_DATASET), "--output-dir", str(without_context)]) == 0
    assert (
        main(
            [
                "--input",
                str(SAMPLE_DATASET),
                "--context",
                str(SAMPLE_CONTEXT),
                "--output-dir",
                str(with_context),
            ]
        )
        == 0
    )

    profile_without_context = json.loads((without_context / PROFILE_FILE_NAME).read_text(encoding="utf-8"))
    profile_with_context = json.loads((with_context / PROFILE_FILE_NAME).read_text(encoding="utf-8"))
    profile_text = (with_context / PROFILE_FILE_NAME).read_text(encoding="utf-8")

    assert profile_with_context == profile_without_context
    assert "raw_rows" not in profile_text
    assert "example_values" not in profile_text
    assert "top_values" not in profile_text
    assert "distinct_values" not in profile_text
    assert "context_metadata" not in profile_text
    assert "suggested_tests" not in profile_text


def test_cli_context_without_input_fails_cleanly(tmp_path, capsys):
    """--context should require --input so field references can be checked."""
    exit_code = main(["--context", str(SAMPLE_CONTEXT), "--output-dir", str(tmp_path / "outputs")])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--context requires --input" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / TRACE_FILE_NAME).exists()


def test_cli_sheet_without_input_fails_cleanly(tmp_path, capsys):
    """--sheet should require --input and avoid falling into scaffold mode."""
    exit_code = main(["--sheet", "Customers", "--output-dir", str(tmp_path / "outputs")])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--sheet requires --input" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / TRACE_FILE_NAME).exists()


def test_cli_invalid_context_fails_cleanly(tmp_path, capsys):
    """Invalid context YAML should return non-zero without a traceback."""
    context_path = tmp_path / "bad_context.yaml"
    context_path.write_text("preferred_strictness: aggressive\n", encoding="utf-8")

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(context_path),
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Invalid preferred_strictness" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / PROFILE_FILE_NAME).exists()


def test_cli_unsupported_extension_fails_cleanly(tmp_path, capsys):
    """Unsupported input files should return non-zero without a traceback."""
    input_path = tmp_path / "customers.txt"
    input_path.write_text("id\n1\n", encoding="utf-8")

    exit_code = main(["--input", str(input_path), "--output-dir", str(tmp_path / "outputs")])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Unsupported input file extension" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / PROFILE_FILE_NAME).exists()


def test_cli_csv_with_sheet_fails_cleanly(tmp_path, capsys):
    """CSV plus --sheet should be rejected with a useful user error."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    exit_code = main(["--input", str(csv_path), "--sheet", "Sheet1", "--output-dir", str(tmp_path / "outputs")])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--sheet can only be used" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / PROFILE_FILE_NAME).exists()


def test_help_works(capsys):
    """The CLI should provide argparse help output."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--input" in output
    assert "--sheet" in output
    assert "--context" in output
    assert "--output-dir" in output


def test_version_works(capsys):
    """The CLI should print its installed package version."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "data-test-suggestion-agent" in output
    assert __version__ in output
