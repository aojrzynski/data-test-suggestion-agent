"""Tests for the Data Test Suggestion Agent scaffold CLI."""

from __future__ import annotations

import json

import pytest

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.cli import FUTURE_STAGES, TRACE_FILE_NAME, main


def test_cli_writes_scaffold_trace(tmp_path, capsys):
    """The CLI should create the output directory and write a scaffold trace."""
    output_dir = tmp_path / "outputs"

    exit_code = main(["--output-dir", str(output_dir)])

    trace_path = output_dir / TRACE_FILE_NAME
    assert exit_code == 0
    assert output_dir.is_dir()
    assert trace_path.is_file()
    assert str(trace_path) in capsys.readouterr().out

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["run_status"] == "scaffold_completed"
    assert trace["message"].startswith("Scaffold run completed")
    assert trace["package_version"] == __version__
    assert trace["stages"] == {stage: "not_implemented" for stage in FUTURE_STAGES}


def test_help_works(capsys):
    """The CLI should provide argparse help output."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "--output-dir" in capsys.readouterr().out


def test_version_works(capsys):
    """The CLI should print its installed package version."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "data-test-suggestion-agent" in output
    assert __version__ in output
