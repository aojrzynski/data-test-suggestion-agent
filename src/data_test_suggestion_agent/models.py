"""Typed data models for dataset intake and safe profiling artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetMetadata:
    """Metadata describing an ingested dataset without storing row values."""

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
    """Safe aggregate profile evidence for an ingested dataset."""

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
