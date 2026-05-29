# Data Test Suggestion Agent

Data Test Suggestion Agent is a local-first Python CLI project that will eventually help answer:

> What data tests should we add for this dataset?

The intended direction is to combine deterministic evidence collection with reviewable candidate test suggestions. If LLM-assisted candidate generation is added later, it will be bounded and optional. The agent will eventually produce reviewable candidate data tests, not automatically approved test coverage. Human reviewers decide what becomes official.

## Current status

The project now supports deterministic dataset intake and safe aggregate profiling for local files. It can read CSV, XLSX, and XLSM inputs, then write JSON artifacts describing dataset metadata and column-level aggregate evidence.

This version still does **not** suggest tests, call an LLM, validate candidate tests, execute tests, or produce reports. `dataset_profile.json` is safe aggregate evidence for later review workflows, not raw data and not a decision about which tests are correct or complete.

## What is implemented

- a Python package named `data_test_suggestion_agent`
- a CLI command named `data-test-suggestion-agent`
- no-input scaffold trace output
- CSV intake
- XLSX/XLSM intake with optional `--sheet` selection
- dataset metadata capture
- safe aggregate profiling in `dataset_profile.json`
- trace metadata for dataset intake and profiling stages
- pytest coverage for intake, profiling, and CLI behavior

## What is intentionally not implemented yet

This version does not include:

- YAML context files
- evidence payload construction for an LLM
- OpenAI or other LLM calls
- candidate test models
- test suggestion generation
- test validation
- test execution
- suggested test YAML output
- markdown reports
- legal, privacy, compliance, correctness, or completeness verdicts

## Quick start

Create and activate a virtual environment, then install the package in editable mode with test dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the tests:

```bash
pytest
```

Use the CLI:

```bash
data-test-suggestion-agent --help
data-test-suggestion-agent --version
```

Run no-input scaffold mode:

```bash
data-test-suggestion-agent --output-dir outputs
```

Profile the synthetic customer sample dataset:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --output-dir outputs
```

Profile an Excel workbook and select a sheet explicitly:

```bash
data-test-suggestion-agent \
  --input path/to/workbook.xlsx \
  --sheet Customers \
  --output-dir outputs
```

## Expected output artifacts

A no-input scaffold run creates:

```text
outputs/data_test_trace.json
```

A dataset profiling run creates:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
```

`data_test_trace.json` records the run status, package metadata, artifact paths, and stage status. In profiling mode, `dataset_intake` and `profiling` are marked `completed`, while future stages such as context loading, LLM suggestions, validation, execution, and reporting remain `not_implemented`.

`dataset_profile.json` contains aggregate evidence such as row count, column count, column names, pandas dtypes, null counts, unique counts, numeric bounds/means, text length statistics, date parse statistics, and cautious deterministic candidate hints. It intentionally avoids raw rows, example values, top values, and distinct value lists.

## Authority boundary

This project is designed around human review. Future versions may generate candidate tests, but those candidates should be treated as suggestions for review. The tool should not claim that suggested tests are complete, correct, or approved without human decision-making.

The current implementation does not send raw rows to any model, does not call an LLM, does not execute arbitrary code, and does not make legal, privacy, or compliance verdicts.
