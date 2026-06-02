"""Tests for the Data Test Suggestion Agent CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_test_suggestion_agent import __version__
from data_test_suggestion_agent.cli import FUTURE_STAGES, main
from data_test_suggestion_agent.output_writers import (
    PAYLOAD_FILE_NAME,
    PROFILE_FILE_NAME,
    REJECTED_SUGGESTIONS_FILE_NAME,
    LLM_CANDIDATE_TESTS_FILE_NAME,
    TEST_EXECUTION_RESULTS_FILE_NAME,
    TRACE_FILE_NAME,
    VALIDATED_SUGGESTIONS_FILE_NAME,
)

SAMPLE_DATASET = Path("sample_data/customers/customers_for_test_suggestions.csv")
SAMPLE_CONTEXT = Path("config/examples/customer_dataset_context.yaml")
VALID_CANDIDATES = Path("config/examples/customer_candidate_tests.json")
MIXED_CANDIDATES = Path("config/examples/customer_candidate_tests_with_rejections.json")


def test_cli_writes_scaffold_trace_without_profile(tmp_path, capsys):
    """No-input mode should keep scaffold behavior and avoid profile output."""
    output_dir = tmp_path / "outputs"

    exit_code = main(["--output-dir", str(output_dir)])

    trace_path = output_dir / TRACE_FILE_NAME
    assert exit_code == 0
    assert output_dir.is_dir()
    assert trace_path.is_file()
    assert not (output_dir / PROFILE_FILE_NAME).exists()
    assert not (output_dir / PAYLOAD_FILE_NAME).exists()
    assert not (output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).exists()
    assert not (output_dir / REJECTED_SUGGESTIONS_FILE_NAME).exists()
    assert not (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).exists()
    assert str(trace_path) in capsys.readouterr().out

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["run_status"] == "scaffold_completed"
    assert trace["message"].startswith("Scaffold run completed")
    assert trace["package_version"] == __version__
    assert set(trace["stages"]) == set(FUTURE_STAGES)
    assert trace["stages"]["dataset_intake"] == "not_requested"
    assert trace["stages"]["profiling"] == "not_requested"
    assert trace["stages"]["context_loading"] == "not_requested"
    assert trace["stages"]["candidate_loading"] == "not_requested"
    assert trace["stages"]["suggestion_validation"] == "not_requested"
    assert trace["stages"]["test_execution"] == "not_requested"


def test_cli_input_mode_writes_trace_profile_and_payload(tmp_path, capsys):
    """Input mode should write trace, profile, payload, and completed stages."""
    output_dir = tmp_path / "outputs"

    exit_code = main(["--input", str(SAMPLE_DATASET), "--output-dir", str(output_dir)])

    trace_path = output_dir / TRACE_FILE_NAME
    profile_path = output_dir / PROFILE_FILE_NAME
    payload_path = output_dir / PAYLOAD_FILE_NAME
    assert exit_code == 0
    assert trace_path.is_file()
    assert profile_path.is_file()
    assert payload_path.is_file()
    assert not (output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).exists()
    assert not (output_dir / REJECTED_SUGGESTIONS_FILE_NAME).exists()
    assert not (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).exists()
    output = capsys.readouterr().out
    assert str(trace_path) in output
    assert str(profile_path) in output
    assert str(payload_path) in output

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["run_status"] == "evidence_payload_completed"
    assert trace["stages"]["dataset_intake"] == "completed"
    assert trace["stages"]["profiling"] == "completed"
    assert trace["stages"]["context_loading"] == "not_requested"
    assert trace["stages"]["evidence_payload"] == "completed"
    assert trace["stages"]["candidate_loading"] == "not_requested"
    assert trace["stages"]["suggestion_validation"] == "not_requested"
    assert trace["stages"]["test_execution"] == "not_requested"
    assert trace["stages"]["llm_suggestions"] == "not_requested"
    assert "context_metadata" not in trace
    assert trace["dataset_metadata"]["file_name"] == "customers_for_test_suggestions.csv"
    assert trace["dataset_metadata"]["row_count"] == 24
    assert trace["artifact_paths"]["dataset_profile"] == str(profile_path)
    assert trace["artifact_paths"]["test_suggestion_payload"] == str(payload_path)

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["payload_metadata"]["contains_raw_rows"] is False
    assert payload["authority_boundary"]["llm_called"] is False
    assert payload["authority_boundary"]["candidate_tests_generated"] is False
    assert payload["human_context"]["provided"] is False
    payload_text = payload_path.read_text(encoding="utf-8")
    assert "alex.rivera@example.com" not in payload_text
    assert "blair.chen@example.com" not in payload_text
    assert "CUST-0001" not in payload_text

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["row_count"] == 24
    assert profile["column_count"] == 9
    assert "alex.rivera@example.com" not in profile_path.read_text(encoding="utf-8")


def test_cli_input_with_context_writes_trace_profile_and_payload(tmp_path, capsys):
    """Input plus context mode should write all artifacts and summarize context."""
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
    payload_path = output_dir / PAYLOAD_FILE_NAME
    assert exit_code == 0
    assert trace_path.is_file()
    assert profile_path.is_file()
    assert payload_path.is_file()
    assert str(trace_path) in capsys.readouterr().out

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["stages"]["dataset_intake"] == "completed"
    assert trace["stages"]["profiling"] == "completed"
    assert trace["stages"]["context_loading"] == "completed"
    assert trace["stages"]["evidence_payload"] == "completed"
    assert trace["stages"]["llm_suggestions"] == "not_requested"
    assert trace["artifact_paths"]["test_suggestion_payload"] == str(payload_path)
    context_metadata = trace["context_metadata"]
    assert context_metadata["context_path"] == str(SAMPLE_CONTEXT)
    assert context_metadata["context_file_name"] == SAMPLE_CONTEXT.name
    assert context_metadata["context_loading"] == "completed"
    assert context_metadata["dataset_name"] == "synthetic_customer_dataset"
    assert context_metadata["preferred_strictness"] == "standard"
    assert context_metadata["referenced_field_count"] == 8
    assert context_metadata["missing_context_fields"] == []
    assert context_metadata["context_warning_count"] == 0

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["human_context"]["provided"] is True
    assert payload["human_context"]["dataset_name"] == "synthetic_customer_dataset"
    assert payload["human_context"]["preferred_strictness"] == "standard"
    assert payload["human_context"]["business_caveat_count"] == 2
    assert payload["human_context"]["field_note_count"] == 2

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
    assert not (tmp_path / "outputs" / PAYLOAD_FILE_NAME).exists()


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
    assert not (tmp_path / "outputs" / PAYLOAD_FILE_NAME).exists()


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
    assert not (tmp_path / "outputs" / PAYLOAD_FILE_NAME).exists()


def test_help_works(capsys):
    """The CLI should provide argparse help output."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--input" in output
    assert "--sheet" in output
    assert "--context" in output
    assert "--candidates" in output
    assert "--output-dir" in output


def test_version_works(capsys):
    """The CLI should print its installed package version."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "data-test-suggestion-agent" in output
    assert __version__ in output


def test_cli_input_with_candidates_writes_validation_artifacts(tmp_path):
    """Input plus candidates should write validation artifacts and trace counts."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--candidates",
            str(VALID_CANDIDATES),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    for file_name in (
        TRACE_FILE_NAME,
        PROFILE_FILE_NAME,
        PAYLOAD_FILE_NAME,
        VALIDATED_SUGGESTIONS_FILE_NAME,
        REJECTED_SUGGESTIONS_FILE_NAME,
    ):
        assert (output_dir / file_name).is_file()
        json.loads((output_dir / file_name).read_text(encoding="utf-8"))

    trace = json.loads((output_dir / TRACE_FILE_NAME).read_text(encoding="utf-8"))
    assert trace["stages"]["candidate_loading"] == "completed"
    assert trace["stages"]["suggestion_validation"] == "completed"
    assert trace["stages"]["test_execution"] == "not_requested"
    assert not (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).exists()
    assert trace["candidate_validation"]["input_candidate_count"] == 6
    assert trace["candidate_validation"]["validated_candidate_count"] == 6
    assert trace["candidate_validation"]["rejected_candidate_count"] == 0

    validated = json.loads(
        (output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).read_text(encoding="utf-8")
    )
    assert validated["candidate_tests_generated_by_this_agent"] is False
    assert validated["llm_called"] is False
    assert validated["validated_candidates_are_approved_tests"] is False
    assert validated["tests_executed"] is False


def test_cli_input_with_context_and_candidates_writes_all_five_artifacts(tmp_path):
    """Context can add validation notes without changing the artifact set."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(SAMPLE_CONTEXT),
            "--candidates",
            str(VALID_CANDIDATES),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).is_file()
    assert (output_dir / REJECTED_SUGGESTIONS_FILE_NAME).is_file()
    trace = json.loads((output_dir / TRACE_FILE_NAME).read_text(encoding="utf-8"))
    assert trace["stages"]["context_loading"] == "completed"
    assert trace["stages"]["suggestion_validation"] == "completed"
    assert trace["artifact_paths"]["validated_test_suggestions"] == str(
        output_dir / VALIDATED_SUGGESTIONS_FILE_NAME
    )


def test_cli_candidates_without_input_fails_cleanly(tmp_path, capsys):
    """--candidates should require --input and avoid scaffold mode."""
    exit_code = main(
        ["--candidates", str(VALID_CANDIDATES), "--output-dir", str(tmp_path / "outputs")]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--candidates requires --input" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / TRACE_FILE_NAME).exists()


def test_cli_invalid_candidate_json_fails_cleanly(tmp_path, capsys):
    """Invalid candidate JSON should fail without validation artifacts or traceback."""
    candidate_path = tmp_path / "bad_candidates.json"
    candidate_path.write_text("{not json", encoding="utf-8")
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--candidates",
            str(candidate_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Malformed candidate JSON" in captured.err
    assert "Traceback" not in captured.err
    assert not (output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).exists()
    assert not (output_dir / REJECTED_SUGGESTIONS_FILE_NAME).exists()
    assert not (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).exists()


def test_cli_mixed_candidates_exit_zero_and_write_rejections(tmp_path):
    """Mixed candidate fixtures should complete validation even with rejections."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(SAMPLE_CONTEXT),
            "--candidates",
            str(MIXED_CANDIDATES),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    rejected = json.loads(
        (output_dir / REJECTED_SUGGESTIONS_FILE_NAME).read_text(encoding="utf-8")
    )
    assert rejected["summary"]["validated_count"] == 2
    assert rejected["summary"]["rejected_count"] == 6
    reason_codes = {
        reason["reason_code"]
        for candidate in rejected["rejected_candidates"]
        for reason in candidate["rejection_reasons"]
    }
    assert "unknown_column" in reason_codes
    assert "unsupported_test_type" in reason_codes
    assert "profile_type_mismatch" in reason_codes
    assert "suspicious_execution_field" in reason_codes
    assert "duplicate_test_id" in reason_codes


def test_validated_and_rejected_artifacts_do_not_include_raw_dataset_samples(tmp_path):
    """Validation artifacts should not leak source row samples from the dataset."""
    output_dir = tmp_path / "outputs"

    assert (
        main(
            [
                "--input",
                str(SAMPLE_DATASET),
                "--candidates",
                str(VALID_CANDIDATES),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    validation_text = (
        (output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).read_text(encoding="utf-8")
        + (output_dir / REJECTED_SUGGESTIONS_FILE_NAME).read_text(encoding="utf-8")
    )
    assert "alex.rivera@example.com" not in validation_text
    assert "blair.chen@example.com" not in validation_text
    assert "CUST-0001" not in validation_text


def test_project_declares_openai_only_as_optional_llm_dependency():
    """Runtime dependencies should keep OpenAI out of base installs."""
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8").lower()

    dependencies_section = pyproject_text.split("[project.optional-dependencies]")[0]
    assert "openai" not in dependencies_section
    assert "llm" in pyproject_text
    assert "openai" in pyproject_text


def test_cli_input_with_candidates_and_execute_writes_execution_artifact(tmp_path):
    """Execution mode should write aggregate-only execution results and trace counts."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--candidates",
            str(VALID_CANDIDATES),
            "--execute-candidates",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    for file_name in (
        TRACE_FILE_NAME,
        PROFILE_FILE_NAME,
        PAYLOAD_FILE_NAME,
        VALIDATED_SUGGESTIONS_FILE_NAME,
        REJECTED_SUGGESTIONS_FILE_NAME,
        TEST_EXECUTION_RESULTS_FILE_NAME,
    ):
        assert (output_dir / file_name).is_file()
        json.loads((output_dir / file_name).read_text(encoding="utf-8"))

    trace = json.loads((output_dir / TRACE_FILE_NAME).read_text(encoding="utf-8"))
    assert trace["run_status"] == "test_execution_completed"
    assert trace["stages"]["test_execution"] == "completed"
    assert trace["test_execution"] == {
        "executed_candidate_count": 6,
        "passed_candidate_count": 6,
        "failed_candidate_count": 0,
        "test_execution_results_path": str(output_dir / TEST_EXECUTION_RESULTS_FILE_NAME),
    }
    assert trace["artifact_paths"]["test_execution_results"] == str(
        output_dir / TEST_EXECUTION_RESULTS_FILE_NAME
    )

    execution = json.loads(
        (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).read_text(encoding="utf-8")
    )
    assert execution["candidate_tests_generated_by_this_agent"] is False
    assert execution["llm_called"] is False
    assert execution["validated_candidates_are_approved_tests"] is False
    assert execution["tests_executed"] is True
    assert execution["execution_is_local_only"] is True
    assert execution["raw_rows_included"] is False
    assert execution["example_values_included"] is False
    assert execution["summary"]["executed_count"] == 6
    assert all(result["status"] == "passed" for result in execution["execution_results"])


def test_cli_input_with_context_candidates_and_execute_writes_all_six_artifacts(tmp_path):
    """Context plus execution mode should validate, execute, and write all artifacts."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(SAMPLE_CONTEXT),
            "--candidates",
            str(VALID_CANDIDATES),
            "--execute-candidates",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    for file_name in (
        TRACE_FILE_NAME,
        PROFILE_FILE_NAME,
        PAYLOAD_FILE_NAME,
        VALIDATED_SUGGESTIONS_FILE_NAME,
        REJECTED_SUGGESTIONS_FILE_NAME,
        TEST_EXECUTION_RESULTS_FILE_NAME,
    ):
        assert (output_dir / file_name).is_file()
    trace = json.loads((output_dir / TRACE_FILE_NAME).read_text(encoding="utf-8"))
    assert trace["stages"]["context_loading"] == "completed"
    assert trace["stages"]["test_execution"] == "completed"


def test_cli_execute_candidates_without_input_fails_cleanly(tmp_path, capsys):
    """Execution requires an input dataset and should not write scaffold artifacts."""
    output_dir = tmp_path / "outputs"

    exit_code = main(["--execute-candidates", "--output-dir", str(output_dir)])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--execute-candidates requires --input" in captured.err
    assert "Traceback" not in captured.err
    assert not (output_dir / TRACE_FILE_NAME).exists()


def test_cli_execute_candidates_without_candidates_fails_cleanly(tmp_path, capsys):
    """Execution requires candidate input so rejected candidates cannot be run."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--execute-candidates",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--execute-candidates requires --candidates" in captured.err
    assert "Traceback" not in captured.err
    assert not (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).exists()


def test_cli_mixed_candidates_with_execute_runs_only_validated_candidates(tmp_path):
    """Rejected candidates should not be executed, and failed checks should exit zero."""
    output_dir = tmp_path / "outputs"

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(SAMPLE_CONTEXT),
            "--candidates",
            str(MIXED_CANDIDATES),
            "--execute-candidates",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    execution = json.loads(
        (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).read_text(encoding="utf-8")
    )
    executed_ids = {result["test_id"] for result in execution["execution_results"]}
    assert execution["summary"]["validated_candidate_count"] == 2
    assert execution["summary"]["executed_count"] == 2
    assert executed_ids == {"customer_id_not_null", "customer_status_allowed_values"}
    assert "unknown_column_not_null" not in executed_ids
    assert "unsafe_code_candidate" not in executed_ids


def test_execution_results_do_not_include_raw_dataset_samples(tmp_path):
    """Execution artifacts should not expose raw rows, example values, or failing values."""
    output_dir = tmp_path / "outputs"

    assert (
        main(
            [
                "--input",
                str(SAMPLE_DATASET),
                "--candidates",
                str(VALID_CANDIDATES),
                "--execute-candidates",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    execution_text = (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).read_text(
        encoding="utf-8"
    )
    assert "alex.rivera@example.com" not in execution_text
    assert "blair.chen@example.com" not in execution_text
    assert "CUST-0001" not in execution_text
    assert "raw_rows_included\": true" not in execution_text
    assert "example_values_included\": true" not in execution_text
    assert "duplicate_values" not in execution_text
    assert "unexpected_values" not in execution_text
    assert "failing_values" not in execution_text


def _generated_candidates() -> list[dict[str, object]]:
    """Return deterministic fake LLM candidates for CLI tests."""
    return [
        {
            "test_id": "customer_id_not_null_generated",
            "test_type": "not_null",
            "column": "customer_id",
            "severity": "high",
            "parameters": {},
            "rationale": "customer_id is important according to safe evidence.",
            "suggested_by": "llm_candidate",
        },
        {
            "test_id": "unknown_generated",
            "test_type": "not_null",
            "column": "not_a_column",
            "severity": "medium",
            "parameters": {},
            "rationale": "This candidate should be rejected deterministically.",
            "suggested_by": "llm_candidate",
        },
    ]


def test_cli_generate_candidates_without_input_fails_cleanly(tmp_path, capsys):
    """LLM generation requires a loaded dataset and safe payload."""
    exit_code = main(["--generate-candidates", "--output-dir", str(tmp_path / "outputs")])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--generate-candidates requires --input" in captured.err
    assert "Traceback" not in captured.err


def test_cli_generate_candidates_and_candidates_together_fail_cleanly(tmp_path, capsys):
    """Manual and LLM candidate sources should be mutually exclusive."""
    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--candidates",
            str(VALID_CANDIDATES),
            "--generate-candidates",
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "use either --candidates" in captured.err
    assert "Traceback" not in captured.err


def test_cli_generate_candidates_without_model_fails_cleanly(tmp_path, capsys, monkeypatch):
    """LLM generation should require explicit model configuration."""
    monkeypatch.delenv("DATA_TEST_AGENT_LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    exit_code = main(
        ["--input", str(SAMPLE_DATASET), "--generate-candidates", "--output-dir", str(tmp_path / "outputs")]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "--llm-model or DATA_TEST_AGENT_LLM_MODEL" in captured.err
    assert "Traceback" not in captured.err


def test_cli_generate_candidates_without_api_key_fails_cleanly(tmp_path, capsys, monkeypatch):
    """LLM generation should require OPENAI_API_KEY without exposing it."""
    monkeypatch.setenv("DATA_TEST_AGENT_LLM_MODEL", "test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main(
        ["--input", str(SAMPLE_DATASET), "--generate-candidates", "--output-dir", str(tmp_path / "outputs")]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "outputs" / LLM_CANDIDATE_TESTS_FILE_NAME).exists()


def test_cli_generated_candidate_mode_writes_llm_validation_artifacts(tmp_path, monkeypatch):
    """Generated candidates should be written and then deterministically validated."""
    output_dir = tmp_path / "outputs"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "data_test_suggestion_agent.cli.generate_candidate_tests_with_openai",
        lambda **kwargs: _generated_candidates(),
    )

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--context",
            str(SAMPLE_CONTEXT),
            "--generate-candidates",
            "--llm-model",
            "test-model",
            "--max-candidates",
            "8",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    for file_name in (
        TRACE_FILE_NAME,
        PROFILE_FILE_NAME,
        PAYLOAD_FILE_NAME,
        LLM_CANDIDATE_TESTS_FILE_NAME,
        VALIDATED_SUGGESTIONS_FILE_NAME,
        REJECTED_SUGGESTIONS_FILE_NAME,
    ):
        assert (output_dir / file_name).is_file()
    assert not (output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).exists()

    trace = json.loads((output_dir / TRACE_FILE_NAME).read_text(encoding="utf-8"))
    assert trace["run_status"] == "llm_candidate_generation_completed"
    assert trace["stages"]["llm_suggestions"] == "completed"
    assert trace["stages"]["candidate_loading"] == "not_applicable"
    assert trace["stages"]["suggestion_validation"] == "completed"
    assert trace["llm_generation"]["candidate_source"] == "llm_generation"
    assert trace["llm_generation"]["raw_rows_sent_to_llm"] is False
    assert trace["llm_generation"]["generated_candidate_count"] == 2
    assert trace["candidate_validation"]["validated_candidate_count"] == 1
    assert trace["candidate_validation"]["rejected_candidate_count"] == 1

    llm_artifact = json.loads((output_dir / LLM_CANDIDATE_TESTS_FILE_NAME).read_text(encoding="utf-8"))
    assert llm_artifact["candidate_tests_generated_by_this_agent"] is True
    assert llm_artifact["llm_called"] is True
    assert llm_artifact["raw_rows_included"] is False
    assert llm_artifact["candidate_count"] == 2

    validated = json.loads((output_dir / VALIDATED_SUGGESTIONS_FILE_NAME).read_text(encoding="utf-8"))
    rejected = json.loads((output_dir / REJECTED_SUGGESTIONS_FILE_NAME).read_text(encoding="utf-8"))
    assert validated["candidate_tests_generated_by_this_agent"] is True
    assert validated["llm_called"] is True
    assert validated["validated_candidates_are_approved_tests"] is False
    assert rejected["candidate_tests_generated_by_this_agent"] is True
    assert rejected["llm_called"] is True


def test_cli_generated_candidate_mode_with_execution_writes_results(tmp_path, monkeypatch):
    """Generated validated candidates can be executed locally and failures exit zero."""
    output_dir = tmp_path / "outputs"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATA_TEST_AGENT_LLM_MODEL", "test-model")
    monkeypatch.setattr(
        "data_test_suggestion_agent.cli.generate_candidate_tests_with_openai",
        lambda **kwargs: _generated_candidates(),
    )

    exit_code = main(
        [
            "--input",
            str(SAMPLE_DATASET),
            "--generate-candidates",
            "--execute-candidates",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    execution = json.loads((output_dir / TEST_EXECUTION_RESULTS_FILE_NAME).read_text(encoding="utf-8"))
    assert execution["candidate_tests_generated_by_this_agent"] is True
    assert execution["llm_called"] is True
    assert execution["validated_candidates_are_approved_tests"] is False
    assert execution["summary"]["validated_candidate_count"] == 1
    executed_ids = {result["test_id"] for result in execution["execution_results"]}
    assert executed_ids == {"customer_id_not_null_generated"}
    assert "unknown_generated" not in executed_ids


def test_llm_candidate_artifact_does_not_include_raw_dataset_samples(tmp_path, monkeypatch):
    """LLM artifact should contain parsed candidates and safe metadata only."""
    output_dir = tmp_path / "outputs"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "data_test_suggestion_agent.cli.generate_candidate_tests_with_openai",
        lambda **kwargs: _generated_candidates(),
    )

    assert (
        main(
            [
                "--input",
                str(SAMPLE_DATASET),
                "--generate-candidates",
                "--llm-model",
                "test-model",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    llm_text = (output_dir / LLM_CANDIDATE_TESTS_FILE_NAME).read_text(encoding="utf-8")
    assert "alex.rivera@example.com" not in llm_text
    assert "blair.chen@example.com" not in llm_text
    assert "CUST-0001" not in llm_text
    assert "raw_rows_included\": true" not in llm_text
    assert "example_values_included\": true" not in llm_text
