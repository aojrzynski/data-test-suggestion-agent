"""Dataset intake helpers for supported local file formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from data_test_suggestion_agent.models import DatasetMetadata

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}


class IntakeError(ValueError):
    """Expected user-facing dataset intake failure."""


@dataclass(frozen=True)
class IngestedDataset:
    """A loaded DataFrame plus metadata safe to include in trace artifacts."""

    dataframe: pd.DataFrame
    metadata: DatasetMetadata


def load_dataset(input_path: str, sheet_name: str | None = None) -> IngestedDataset:
    """Load a supported dataset and return its DataFrame with metadata.

    CSV files do not have worksheets, so passing ``sheet_name`` for a CSV is a
    user error. Excel handling is intentionally explicit so traces can record
    which sheet was actually profiled.
    """
    path = Path(input_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise IntakeError(f"Unsupported input file extension '{extension or '<none>'}'. Supported formats: {supported}.")

    if extension == ".csv" and sheet_name is not None:
        raise IntakeError("--sheet can only be used with Excel files (.xlsx or .xlsm), not CSV files.")

    try:
        if extension == ".csv":
            dataframe = pd.read_csv(path)
            loaded_sheet_name = None
        else:
            dataframe, loaded_sheet_name = _read_excel(path, sheet_name)
    except FileNotFoundError as exc:
        raise IntakeError(f"Input file not found: {input_path}") from exc
    except ValueError as exc:
        raise IntakeError(f"Could not load dataset: {exc}") from exc
    except OSError as exc:
        raise IntakeError(f"Could not read input file: {exc}") from exc

    metadata = DatasetMetadata(
        input_path=input_path,
        file_name=path.name,
        file_extension=extension,
        sheet_name=loaded_sheet_name,
        row_count=int(len(dataframe)),
        column_count=int(len(dataframe.columns)),
        columns=[str(column) for column in dataframe.columns],
    )
    return IngestedDataset(dataframe=dataframe, metadata=metadata)


def _read_excel(path: Path, requested_sheet_name: str | None) -> tuple[pd.DataFrame, str]:
    """Read an Excel workbook and return the selected sheet name."""
    try:
        workbook = pd.ExcelFile(path, engine="openpyxl")
    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except OSError:
        raise
    except Exception as exc:  # pragma: no cover - depends on openpyxl internals
        raise IntakeError(f"Could not open Excel workbook: {exc}") from exc

    available_sheets = [str(sheet) for sheet in workbook.sheet_names]
    if not available_sheets:
        raise IntakeError("Excel workbook does not contain any sheets.")

    # Defaulting to the first workbook sheet mirrors spreadsheet application
    # behavior while still recording the resolved sheet for reproducibility.
    loaded_sheet_name = requested_sheet_name or available_sheets[0]
    if loaded_sheet_name not in available_sheets:
        available = ", ".join(available_sheets)
        raise IntakeError(f"Sheet '{loaded_sheet_name}' was not found. Available sheets: {available}.")

    dataframe = workbook.parse(sheet_name=loaded_sheet_name)
    return dataframe, loaded_sheet_name
