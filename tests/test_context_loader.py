"""Tests for human-authored YAML context loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_test_suggestion_agent.context_loader import ContextLoadError, load_context, summarize_context


def _write_context(tmp_path: Path, text: str) -> Path:
    """Write context YAML text to a temporary file."""
    path = tmp_path / "context.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_valid_yaml_context(tmp_path):
    """A complete context YAML file should load into a typed model."""
    path = _write_context(
        tmp_path,
        """
dataset_name: synthetic_customer_dataset
dataset_purpose: Safe profiling demo.
expected_grain: one row per customer
important_fields:
  - customer_id
known_id_fields:
  - customer_id
known_date_fields:
  - signup_date
known_categorical_fields:
  - customer_status
business_caveats:
  - Synthetic demo caveat.
fields_to_ignore:
  - internal_note
preferred_strictness: standard
field_notes:
  customer_id: Synthetic stable customer identifier.
""",
    )

    context = load_context(str(path))

    assert context.dataset_name == "synthetic_customer_dataset"
    assert context.preferred_strictness == "standard"
    assert context.important_fields == ["customer_id"]
    assert context.field_notes == {"customer_id": "Synthetic stable customer identifier."}


def test_applies_defaults_for_omitted_optional_fields(tmp_path):
    """Missing optional fields should become safe defaults."""
    path = _write_context(tmp_path, "dataset_name: small_demo\n")

    context = load_context(str(path))

    assert context.dataset_name == "small_demo"
    assert context.dataset_purpose is None
    assert context.important_fields == []
    assert context.field_notes == {}
    assert context.preferred_strictness == "cautious"


def test_rejects_malformed_yaml(tmp_path):
    """Malformed YAML should produce a clean context loading error."""
    path = _write_context(tmp_path, "dataset_name: [unterminated\n")

    with pytest.raises(ContextLoadError, match="Malformed context YAML"):
        load_context(str(path))


def test_rejects_top_level_non_mapping_yaml(tmp_path):
    """Context YAML must be an object at the top level."""
    path = _write_context(tmp_path, "- customer_id\n- email\n")

    with pytest.raises(ContextLoadError, match="top level must be a mapping"):
        load_context(str(path))


def test_rejects_unknown_top_level_keys(tmp_path):
    """Unexpected context keys should fail instead of being silently ignored."""
    path = _write_context(tmp_path, "dataset_name: demo\nextra_key: value\n")

    with pytest.raises(ContextLoadError, match="Unknown context field"):
        load_context(str(path))


def test_rejects_invalid_preferred_strictness(tmp_path):
    """Only documented strictness values should be accepted."""
    path = _write_context(tmp_path, "preferred_strictness: aggressive\n")

    with pytest.raises(ContextLoadError, match="Invalid preferred_strictness"):
        load_context(str(path))


def test_rejects_list_fields_that_are_not_lists_of_strings(tmp_path):
    """List context fields should not silently accept scalar values."""
    path = _write_context(tmp_path, "important_fields: customer_id\n")

    with pytest.raises(ContextLoadError, match="important_fields.*list of strings"):
        load_context(str(path))


def test_rejects_list_fields_with_non_string_items(tmp_path):
    """List context fields should reject non-string members."""
    path = _write_context(tmp_path, "known_id_fields:\n  - customer_id\n  - 123\n")

    with pytest.raises(ContextLoadError, match="known_id_fields.*list of strings"):
        load_context(str(path))


def test_rejects_field_notes_when_not_mapping(tmp_path):
    """Field notes should be represented as a mapping."""
    path = _write_context(tmp_path, "field_notes:\n  - customer_id\n")

    with pytest.raises(ContextLoadError, match="field_notes.*mapping"):
        load_context(str(path))


def test_rejects_field_notes_when_not_string_to_string(tmp_path):
    """Field notes should have string keys and string values."""
    path = _write_context(tmp_path, "field_notes:\n  customer_id: 123\n")

    with pytest.raises(ContextLoadError, match="string keys to string values"):
        load_context(str(path))


def test_handles_missing_context_files_cleanly(tmp_path):
    """Missing context paths should produce an expected user-facing error."""
    missing = tmp_path / "missing.yaml"

    with pytest.raises(ContextLoadError, match="Context file not found"):
        load_context(str(missing))


def test_dataset_column_cross_check_records_missing_fields_without_failing(tmp_path):
    """Missing context fields should become trace warnings, not hard failures."""
    path = _write_context(
        tmp_path,
        """
important_fields:
  - customer_id
  - missing_column
known_date_fields:
  - signup_date
fields_to_ignore:
  - stale_internal_field
field_notes:
  lifetime_value: Value for profiling demos.
  missing_note_field: Stale note.
""",
    )
    context = load_context(str(path))

    summary = summarize_context(
        context=context,
        context_path=str(path),
        dataset_columns=["customer_id", "signup_date", "lifetime_value"],
    )

    assert summary["context_loading"] == "completed"
    assert summary["referenced_field_count"] == 5
    assert summary["missing_context_fields"] == ["missing_column", "missing_note_field", "stale_internal_field"]
    assert summary["context_warning_count"] == 1
    assert summary["warnings"][0]["warning_type"] == "missing_context_fields"
