"""Typed data models for dataset intake and safe profiling artifacts.

These dataclasses carry evidence between CLI workflow stages. They are kept
plain and JSON-friendly so artifacts, tests, and orchestration code inspect the
same structures rather than translating through a hidden runtime model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetMetadata:
    """Metadata describing an ingested dataset without storing row values.

    This records file identity, shape, resolved worksheet, and column names only.
    It is safe trace evidence about what was loaded, not a preview of source
    records or field contents.
    """

    input_path: str
    file_name: str
    file_extension: str
    sheet_name: str | None
    row_count: int
    column_count: int
    columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the metadata."""
        return asdict(self)


@dataclass(frozen=True)
class DatasetContext:
    """Human-authored dataset context loaded from optional YAML.

    Context captures reviewer-provided meaning such as expected grain, known
    field roles, and caveats. It is human-authored meaning, not source-data
    evidence, and it does not approve or require any generated, accepted, or
    executed data test.
    """

    dataset_name: str | None = None
    dataset_purpose: str | None = None
    expected_grain: str | None = None
    important_fields: list[str] = field(default_factory=list)
    known_id_fields: list[str] = field(default_factory=list)
    known_date_fields: list[str] = field(default_factory=list)
    known_categorical_fields: list[str] = field(default_factory=list)
    business_caveats: list[str] = field(default_factory=list)
    fields_to_ignore: list[str] = field(default_factory=list)
    preferred_strictness: str | None = "cautious"
    field_notes: dict[str, str] = field(default_factory=dict)

    def referenced_fields(self) -> set[str]:
        """Return unique dataset field names referenced by context metadata."""
        fields: set[str] = set()
        fields.update(self.important_fields)
        fields.update(self.known_id_fields)
        fields.update(self.known_date_fields)
        fields.update(self.known_categorical_fields)
        fields.update(self.fields_to_ignore)
        fields.update(self.field_notes.keys())
        return fields

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the context."""
        return asdict(self)


@dataclass(frozen=True)
class ColumnProfile:
    """Safe aggregate profile evidence for one dataset column.

    The profile intentionally stores counts, ratios, broad types, and bounded
    summary statistics only. It does not store raw rows, examples, top values,
    or distinct value lists, because later candidate generation should be based
    on aggregate evidence rather than copied source records.
    """

    name: str
    pandas_dtype: str
    profile_type: str
    row_count: int
    non_null_count: int
    null_count: int
    null_ratio: float
    unique_count: int
    unique_ratio: float
    duplicate_value_count: int
    likely_identifier_candidate: bool
    low_cardinality_candidate: bool
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_mean: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    average_length: float | None = None
    empty_string_count: int | None = None
    parseable_date_count: int | None = None
    parseable_date_ratio: float | None = None
    min_date: str | None = None
    max_date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a compact JSON-serializable profile dictionary."""
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class DatasetProfile:
    """Safe aggregate profile evidence for an ingested dataset.

    This is the dataset-level profile artifact consumed by the safe evidence
    payload and later deterministic candidate validation. It summarizes shape
    and per-column aggregates while preserving the row/value boundary.
    """

    dataset_metadata: DatasetMetadata
    row_count: int
    column_count: int
    columns: list[ColumnProfile] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable profile artifact payload."""
        return {
            "dataset_metadata": self.dataset_metadata.to_dict(),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [column.to_dict() for column in self.columns],
        }
