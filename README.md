# Data Test Suggestion Agent

Data Test Suggestion Agent is a local-first Python CLI project that will eventually help answer:

> What data tests should we add for this dataset?

The intended direction is to combine deterministic evidence collection with reviewable candidate test suggestions. If LLM-assisted candidate generation is added later, it will be bounded and optional. The agent will eventually produce reviewable candidate data tests, not automatically approved test coverage. Human reviewers decide what becomes official.

## Current status

The project now supports deterministic dataset intake, safe aggregate profiling for local files, and optional human-authored YAML context loading. It can read CSV, XLSX, and XLSM inputs, then write JSON artifacts describing dataset metadata, column-level aggregate evidence, and trace-only context metadata.

This version still does **not** suggest tests, call an LLM, validate candidate tests, execute tests, or produce reports. `dataset_profile.json` is safe aggregate evidence for later review workflows, not raw data and not a decision about which tests are correct or complete. Human-authored context can record dataset meaning, but it does not cause test suggestions yet.

## What is implemented

- a Python package named `data_test_suggestion_agent`
- a CLI command named `data-test-suggestion-agent`
- no-input scaffold trace output
- CSV intake
- XLSX/XLSM intake with optional `--sheet` selection
- optional YAML context loading with `--context`
- dataset metadata capture
- safe aggregate profiling in `dataset_profile.json`
- trace metadata for dataset intake, profiling, and context-loading stages
- pytest coverage for intake, profiling, context loading, and CLI behavior

## What is intentionally not implemented yet

This version does not include:

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

Profile the synthetic customer sample dataset with human-authored context:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
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

`data_test_trace.json` records the run status, package metadata, artifact paths, and stage status. In profiling mode, `dataset_intake` and `profiling` are marked `completed`. When `--context` is provided, `context_loading` is marked `completed` and trace metadata records the context path, context file name, optional dataset name, preferred strictness, referenced-field count, and any missing context fields for review. Without `--context`, `context_loading` is marked `not_requested`. Later stages such as evidence payload construction, LLM suggestions, validation, execution, and reporting remain `not_implemented`.

`dataset_profile.json` contains aggregate evidence such as row count, column count, column names, pandas dtypes, null counts, unique counts, numeric bounds/means, text length statistics, date parse statistics, and cautious deterministic candidate hints. It intentionally avoids raw rows, example values, top values, and distinct value lists. Human-authored context is not written into `dataset_profile.json`; it is represented in `data_test_trace.json` for now.

## Optional YAML context

A context file lets a human reviewer describe dataset meaning that deterministic profiling cannot infer reliably, such as expected grain, important fields, known ID/date/categorical fields, business caveats, fields to ignore, and preferred strictness. This context is useful groundwork for later reviewable test-suggestion stages, but the current CLI only loads, validates, summarizes, and records it. It does not generate tests or decide that any test is correct or complete.

If `preferred_strictness` is omitted from context YAML, the loader defaults it to `cautious`. Allowed values are `cautious`, `standard`, and `strict`. Fields referenced by context are checked against the loaded dataset columns. Missing references are recorded as `missing_context_fields` warnings in `data_test_trace.json` instead of failing the run, because they may reflect stale context, renamed columns, or a subset extract rather than a dataset defect.

Expected clean user errors include:

- `--context` requires `--input` so context can be checked against dataset columns.
- `--sheet` requires `--input`.
- `--sheet` is only valid for Excel inputs (`.xlsx` or `.xlsm`).

## Authority boundary

This project is designed around human review. Future versions may generate candidate tests, but those candidates should be treated as suggestions for review. The tool should not claim that suggested tests are complete, correct, or approved without human decision-making.

The current implementation does not send raw rows to any model, does not call an LLM, does not execute arbitrary code, and does not make legal, privacy, or compliance verdicts.
