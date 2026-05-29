"""Safe deterministic dataset profiling."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from data_test_suggestion_agent.models import ColumnProfile, DatasetMetadata, DatasetProfile

DATE_PARSE_THRESHOLD = 0.8
LOW_CARDINALITY_MAX_UNIQUE = 20
LOW_CARDINALITY_MAX_RATIO = 0.2
ID_NAME_PATTERN = re.compile(r"(^id$|_id$|id$|identifier|uuid|key$)", re.IGNORECASE)


def profile_dataset(dataframe: pd.DataFrame, metadata: DatasetMetadata) -> DatasetProfile:
    """Build a safe aggregate profile for an ingested DataFrame.

    This function deliberately stops at deterministic evidence. It does not
    infer official data tests, because uniqueness, accepted values, and similar
    constraints require domain context plus human review in later PRs.
    """
    row_count = int(len(dataframe))
    columns = [profile_column(str(column), series, row_count) for column, series in dataframe.items()]
    return DatasetProfile(
        dataset_metadata=metadata,
        row_count=row_count,
        column_count=int(len(dataframe.columns)),
        columns=columns,
    )


def profile_column(name: str, series: pd.Series, row_count: int) -> ColumnProfile:
    """Return safe aggregate profile evidence for one column."""
    non_null = series.dropna()
    non_null_count = int(non_null.size)
    null_count = int(row_count - non_null_count)
    unique_count = int(series.nunique(dropna=True))
    null_ratio = _safe_ratio(null_count, row_count)
    unique_ratio = _safe_ratio(unique_count, non_null_count)
    duplicate_value_count = int(max(non_null_count - unique_count, 0))
    date_stats = _date_stats(series, non_null)

    likely_identifier = bool(
        row_count > 0
        and unique_ratio >= 0.95
        and null_ratio <= 0.05
        and ID_NAME_PATTERN.search(name)
    )
    low_cardinality = bool(
        row_count > 0
        and unique_count > 0
        and unique_count <= LOW_CARDINALITY_MAX_UNIQUE
        and unique_ratio <= LOW_CARDINALITY_MAX_RATIO
    )

    base: dict[str, Any] = {
        "name": name,
        "pandas_dtype": str(series.dtype),
        "profile_type": _profile_type(series, date_stats),
        "row_count": row_count,
        "non_null_count": non_null_count,
        "null_count": null_count,
        "null_ratio": null_ratio,
        "unique_count": unique_count,
        "unique_ratio": unique_ratio,
        "duplicate_value_count": duplicate_value_count,
        "likely_identifier_candidate": likely_identifier,
        "low_cardinality_candidate": low_cardinality,
    }

    if is_bool_dtype(series):
        pass
    elif is_numeric_dtype(series):
        base.update(_numeric_stats(non_null))
    elif date_stats is None:
        base.update(_text_stats(non_null))

    if date_stats is not None:
        base.update(date_stats)

    return ColumnProfile(**base)


def _profile_type(series: pd.Series, date_stats: dict[str, Any] | None) -> str:
    """Infer a broad profile type from pandas dtype and deterministic parsing."""
    if is_bool_dtype(series):
        return "boolean"
    if is_numeric_dtype(series):
        return "numeric"
    if date_stats is not None:
        return "datetime"
    if series.dtype == "object" or pd.api.types.is_string_dtype(series):
        return "text"
    return "unknown"


def _numeric_stats(non_null: pd.Series) -> dict[str, float | None]:
    """Return numeric aggregates without exposing observed values beyond bounds."""
    if non_null.empty:
        return {"numeric_min": None, "numeric_max": None, "numeric_mean": None}
    numeric = pd.to_numeric(non_null, errors="coerce").dropna()
    if numeric.empty:
        return {"numeric_min": None, "numeric_max": None, "numeric_mean": None}
    return {
        "numeric_min": float(numeric.min()),
        "numeric_max": float(numeric.max()),
        "numeric_mean": float(numeric.mean()),
    }


def _text_stats(non_null: pd.Series) -> dict[str, int | float | None]:
    """Return aggregate text length statistics without sample values."""
    if non_null.empty:
        return {
            "min_length": None,
            "max_length": None,
            "average_length": None,
            "empty_string_count": 0,
        }
    strings = non_null.astype("string")
    lengths = strings.str.len()
    return {
        "min_length": int(lengths.min()),
        "max_length": int(lengths.max()),
        "average_length": float(lengths.mean()),
        "empty_string_count": int((strings == "").sum()),
    }


def _date_stats(series: pd.Series, non_null: pd.Series) -> dict[str, int | float | str] | None:
    """Return date aggregates when a column is natively or strongly date-like."""
    if non_null.empty:
        if is_datetime64_any_dtype(series):
            return {"parseable_date_count": 0, "parseable_date_ratio": 0.0}
        return None

    if is_datetime64_any_dtype(series):
        parsed = pd.to_datetime(non_null, errors="coerce")
    elif series.dtype == "object" or pd.api.types.is_string_dtype(series):
        # Object columns are treated as date-like only when deterministic parsing
        # succeeds for a high proportion of non-null values. Aggregates are enough
        # for later reviewable candidate suggestions; raw date examples are not kept.
        parsed = pd.to_datetime(non_null.astype("string"), errors="coerce", format="mixed")
    else:
        return None

    parseable = parsed.dropna()
    parseable_count = int(parseable.size)
    parseable_ratio = _safe_ratio(parseable_count, int(non_null.size))
    if not is_datetime64_any_dtype(series) and parseable_ratio < DATE_PARSE_THRESHOLD:
        return None

    stats: dict[str, int | float | str] = {
        "parseable_date_count": parseable_count,
        "parseable_date_ratio": parseable_ratio,
    }
    if parseable_count > 0:
        stats["min_date"] = _iso_datetime(parseable.min())
        stats["max_date"] = _iso_datetime(parseable.max())
    return stats


def _iso_datetime(value: Any) -> str:
    """Format a pandas timestamp-like value as an ISO-style string."""
    timestamp = pd.Timestamp(value)
    if timestamp.time() == pd.Timestamp(0).time():
        return timestamp.date().isoformat()
    return timestamp.isoformat()


def _safe_ratio(numerator: int, denominator: int) -> float:
    """Return a rounded ratio with a safe zero denominator fallback."""
    if denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)
