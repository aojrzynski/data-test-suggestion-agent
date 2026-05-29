"""Tests for deterministic dataset intake."""

from __future__ import annotations

import shutil

import pandas as pd
import pytest

from data_test_suggestion_agent.intake import IntakeError, load_dataset


def test_loads_csv_and_records_metadata(tmp_path):
    """CSV intake should load rows and record safe dataset metadata."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("id,name\n1,Ada\n2,Bea\n", encoding="utf-8")

    ingested = load_dataset(str(csv_path))

    assert ingested.dataframe.shape == (2, 2)
    assert ingested.metadata.input_path == str(csv_path)
    assert ingested.metadata.file_name == "customers.csv"
    assert ingested.metadata.file_extension == ".csv"
    assert ingested.metadata.sheet_name is None
    assert ingested.metadata.row_count == 2
    assert ingested.metadata.column_count == 2
    assert ingested.metadata.columns == ["id", "name"]


def test_rejects_sheet_for_csv(tmp_path):
    """CSV intake should reject Excel-only sheet selection."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(IntakeError, match="--sheet can only be used"):
        load_dataset(str(csv_path), sheet_name="Customers")


def test_loads_xlsx_default_first_sheet(tmp_path):
    """Excel intake should default to the first workbook sheet."""
    xlsx_path = tmp_path / "workbook.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame({"id": [1], "name": ["Ada"]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"id": [2], "name": ["Bea"]}).to_excel(writer, sheet_name="Second", index=False)

    ingested = load_dataset(str(xlsx_path))

    assert ingested.dataframe["id"].tolist() == [1]
    assert ingested.metadata.file_extension == ".xlsx"
    assert ingested.metadata.sheet_name == "First"


def test_loads_xlsx_named_sheet_and_records_metadata(tmp_path):
    """Excel intake should support explicit named sheets."""
    xlsx_path = tmp_path / "workbook.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame({"id": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"id": [2, 3]}).to_excel(writer, sheet_name="Customers", index=False)

    ingested = load_dataset(str(xlsx_path), sheet_name="Customers")

    assert ingested.dataframe["id"].tolist() == [2, 3]
    assert ingested.metadata.sheet_name == "Customers"
    assert ingested.metadata.row_count == 2
    assert ingested.metadata.column_count == 1


def test_supports_xlsm_extension_with_openpyxl_compatible_content(tmp_path):
    """XLSM intake should route through openpyxl-compatible Excel reading."""
    xlsx_path = tmp_path / "source.xlsx"
    xlsm_path = tmp_path / "macro_enabled.xlsm"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame({"id": [10]}).to_excel(writer, sheet_name="Customers", index=False)
    shutil.copyfile(xlsx_path, xlsm_path)

    ingested = load_dataset(str(xlsm_path), sheet_name="Customers")

    assert ingested.metadata.file_extension == ".xlsm"
    assert ingested.metadata.sheet_name == "Customers"
    assert ingested.dataframe["id"].tolist() == [10]


def test_rejects_unsupported_extension(tmp_path):
    """Unsupported file types should fail before attempting parsing."""
    txt_path = tmp_path / "customers.txt"
    txt_path.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(IntakeError, match="Unsupported input file extension"):
        load_dataset(str(txt_path))
