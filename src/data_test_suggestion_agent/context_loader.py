"""Load and validate optional human-authored dataset context YAML.

Human-authored context is deliberately kept separate from deterministic dataset
profiling. The profile artifact remains aggregate-only evidence from the source
file, while context metadata is recorded in the trace for later review-oriented
workflow stages.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from data_test_suggestion_agent.models import DatasetContext

# The context schema is intentionally explicit so YAML typos fail cleanly
# instead of silently changing reviewer intent downstream.
ALLOWED_CONTEXT_KEYS = {
    "dataset_name",
    "dataset_purpose",
    "expected_grain",
    "important_fields",
    "known_id_fields",
    "known_date_fields",
    "known_categorical_fields",
    "business_caveats",
    "fields_to_ignore",
    "preferred_strictness",
    "field_notes",
}

# These groups drive simple schema validation: list-valued fields are normalized
# to lists of strings, while scalar metadata remains optional string fields.
LIST_FIELDS = {
    "important_fields",
    "known_id_fields",
    "known_date_fields",
    "known_categorical_fields",
    "business_caveats",
    "fields_to_ignore",
}

STRING_FIELDS = {"dataset_name", "dataset_purpose", "expected_grain"}

PREFERRED_STRICTNESS_VALUES = {"cautious", "standard", "strict"}


class ContextLoadError(ValueError):
    """Expected user-facing context loading or validation failure."""


def load_context(context_path: str) -> DatasetContext:
    """Load a YAML context file and return a validated dataset context.

    YAML is parsed with ``safe_load`` because context files are user-authored
    configuration, not executable input. Missing optional list fields default to
    empty lists, and omitted ``preferred_strictness`` defaults to ``cautious`` so
    later stages can preserve a conservative posture unless the reviewer chooses
    otherwise.
    """
    path = Path(context_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ContextLoadError(f"Context file not found: {context_path}") from exc
    except OSError as exc:
        raise ContextLoadError(f"Could not read context file: {exc}") from exc

    try:
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ContextLoadError(f"Malformed context YAML: {exc}") from exc

    if not isinstance(loaded, Mapping):
        raise ContextLoadError("Context YAML top level must be a mapping/object.")

    unknown_keys = sorted(
        str(key) for key in loaded if str(key) not in ALLOWED_CONTEXT_KEYS
    )
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ContextLoadError(f"Unknown context field(s): {joined}.")

    values: dict[str, Any] = {}
    for field_name in STRING_FIELDS:
        values[field_name] = _optional_string(loaded, field_name)
    for field_name in LIST_FIELDS:
        values[field_name] = _string_list(loaded, field_name)

    values["preferred_strictness"] = _preferred_strictness(loaded)
    values["field_notes"] = _field_notes(loaded)

    return DatasetContext(**values)


def summarize_context(
    *,
    context: DatasetContext,
    context_path: str,
    dataset_columns: list[str],
) -> dict[str, Any]:
    """Return trace-safe metadata for a loaded context and dataset columns.

    Missing referenced fields are warnings rather than hard failures because a
    mismatch can come from stale reviewer context, renamed columns, or a subset
    extract. It is useful trace evidence, but it is not itself a dataset defect
    and must not imply any suggested test.
    """
    referenced_fields = sorted(context.referenced_fields())
    dataset_column_set = {str(column) for column in dataset_columns}
    missing_context_fields = [
        field for field in referenced_fields if field not in dataset_column_set
    ]
    warnings: list[dict[str, Any]] = []
    if missing_context_fields:
        warnings.append(
            {
                "warning_type": "missing_context_fields",
                "message": (
                    "Some fields referenced by the human-authored context were not found "
                    "in the loaded dataset columns. This is recorded for review only."
                ),
                "fields": missing_context_fields,
            }
        )

    return {
        "context_path": context_path,
        "context_file_name": Path(context_path).name,
        "context_loading": "completed",
        "dataset_name": context.dataset_name,
        "preferred_strictness": context.preferred_strictness,
        "referenced_field_count": len(referenced_fields),
        "missing_context_fields": missing_context_fields,
        "context_warning_count": len(warnings),
        "warnings": warnings,
    }


def _optional_string(loaded: Mapping[Any, Any], field_name: str) -> str | None:
    """Validate an optional string context field."""
    if field_name not in loaded or loaded[field_name] is None:
        return None
    if not isinstance(loaded[field_name], str):
        raise ContextLoadError(
            f"Context field '{field_name}' must be a string when provided."
        )
    return loaded[field_name]


def _string_list(loaded: Mapping[Any, Any], field_name: str) -> list[str]:
    """Validate a context list field as a list of strings."""
    if field_name not in loaded or loaded[field_name] is None:
        return []
    value = loaded[field_name]
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise ContextLoadError(
            f"Context field '{field_name}' must be a list of strings."
        )
    return list(value)


def _preferred_strictness(loaded: Mapping[Any, Any]) -> str:
    """Validate preferred strictness or apply the documented cautious default."""
    value = loaded.get("preferred_strictness", "cautious")
    if value is None:
        return "cautious"
    if not isinstance(value, str):
        raise ContextLoadError(
            "Context field 'preferred_strictness' must be a string."
        )
    if value not in PREFERRED_STRICTNESS_VALUES:
        allowed = ", ".join(sorted(PREFERRED_STRICTNESS_VALUES))
        raise ContextLoadError(
            f"Invalid preferred_strictness '{value}'. Allowed values: {allowed}."
        )
    return value


def _field_notes(loaded: Mapping[Any, Any]) -> dict[str, str]:
    """Validate field notes as a string-to-string mapping."""
    if "field_notes" not in loaded or loaded["field_notes"] is None:
        return {}
    value = loaded["field_notes"]
    if not isinstance(value, Mapping):
        raise ContextLoadError(
            "Context field 'field_notes' must be a mapping of string keys to string values."
        )
    if any(
        not isinstance(key, str) or not isinstance(note, str)
        for key, note in value.items()
    ):
        raise ContextLoadError(
            "Context field 'field_notes' must be a mapping of string keys to string values."
        )
    return dict(value)
