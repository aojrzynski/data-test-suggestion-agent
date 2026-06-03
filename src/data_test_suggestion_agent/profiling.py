"""Safe deterministic dataset profiling.

Profiling creates aggregate evidence only: counts, ratios, broad type hints,
and bounded summaries. It intentionally avoids raw rows, sample/example values,
top values, and distinct value lists so later suggestion stages cannot copy
source records into prompts, artifacts, or reports.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from data_test_suggestion_agent.models import ColumnProfile, DatasetMetadata, DatasetProfile

# Object/string columns are considered date-like only when parsing succeeds for
# a strong majority of non-null values; otherwise they stay text/unknown.
DATE_PARSE_THRESHOLD = 0.8
# Low-cardinality flags are review hints for candidate suggestion, not accepted-
# values decisions. The validator still requires supplied allowed values.
LOW_CARDINALITY_MAX_UNIQUE = 20
LOW_CARDINALITY_MAX_RATIO = 0.2
# Name matching contributes to a cautious identifier hint; uniqueness/null
# aggregates are still required, and the hint is not a uniqueness rule.
ID_NAME_PATTERN = re.compile(r"(^id$|_id$|id$|identifier|uuid|key$)", re.IGNORECASE)


def profile_dataset(dataframe: pd.DataFrame, metadata: DatasetMetadata) -> DatasetProfile:
    """Build a safe aggregate profile for an ingested DataFrame.

    This function deliberately stops at deterministic evidence. It does not
    infer official data tests. It creates evidence for later candidate
    suggestion, validation, and human review.
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
    # Null, non-null, unique, and duplicate counts are safe aggregate evidence:
    # they describe column shape without exposing any observed row values.
    non_null = series.dropna()
    non_null_count = int(non_null.size)
    null_count = int(row_count - non_null_count)
    unique_count = int(series.nunique(dropna=True))
    null_ratio = _safe_ratio(null_count, row_count)
    unique_ratio = _safe_ratio(unique_count, non_null_count)
    duplicate_value_count = int(max(non_null_count - unique_count, 0))
    date_stats = _date_stats(series, non_null)

    # Identifier detection is intentionally a cautious hint based on name,
    # near-uniqueness, and low nulls; it does not assert a final unique key.
    likely_identifier = bool(
        row_count > 0
        and unique_ratio >= 0.95
        and null_ratio <= 0.05
        and ID_NAME_PATTERN.search(name)
    )
    # Low-cardinality is a suggestion/review hint only. Accepted-values tests
    # still need explicit allowed values from a candidate source or context.
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

    # Type-specific branches add only aggregate summaries. Booleans need no
    # extra examples; numeric/text/date summaries use counts, bounds, or lengths.
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
        # Native datetime columns are date-like even when all rows are null.
        if is_datetime64_any_dtype(series):
            return {"parseable_date_count": 0, "parseable_date_ratio": 0.0}
        return None

    if is_datetime64_any_dtype(series):
        # Native datetime dtypes are accepted as date-like before parseability
        # thresholds because pandas has already typed the column as temporal.
        parsed = pd.to_datetime(non_null, errors="coerce")
    elif series.dtype == "object" or pd.api.types.is_string_dtype(series):
        # Object/string columns require high parseability so ordinary text is
        # not mislabeled as dates because a few values happen to parse.
        # Aggregates are enough for reviewable suggestions; raw date examples
        # are not kept.
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
