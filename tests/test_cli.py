"""Tests for the Data Test Suggestion Agent CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.cli import FUTURE_STAGES, main
from data_test_suggestion_agent.output_writers import PROFILE_FILE_NAME, TRACE_FILE_NAME

SAMPLE_DATASET = Path("sample_data/customers/customers_for_test_suggestions.csv")


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
    assert trace["stages"]["llm_suggestions"] == "not_implemented"
    assert trace["dataset_metadata"]["file_name"] == "customers_for_test_suggestions.csv"
    assert trace["dataset_metadata"]["row_count"] == 24
    assert trace["artifact_paths"]["dataset_profile"] == str(profile_path)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["row_count"] == 24
    assert profile["column_count"] == 9
    assert "alex.rivera@example.com" not in profile_path.read_text(encoding="utf-8")


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
    assert "--output-dir" in output


def test_version_works(capsys):
    """The CLI should print its installed package version."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "data-test-suggestion-agent" in output
    assert __version__ in output
