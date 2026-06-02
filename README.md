# Data Test Suggestion Agent

A local-first Python CLI scaffold for a future data test suggestion workflow.

The project is intended to eventually help answer:

> What data tests should we add for this dataset?

The intended direction is to combine deterministic evidence collection with reviewable candidate test suggestions. If LLM-assisted candidate generation is added later, it will be bounded and optional. The agent will eventually produce reviewable candidate data tests, not automatically approved test coverage. Human reviewers decide what becomes official.

## Current status

The project now supports deterministic dataset intake, safe aggregate profiling for local files, optional human-authored YAML context loading, local safe evidence payload construction, and deterministic validation of manually supplied local candidate test suggestions. It can read CSV, XLSX, and XLSM inputs, then write JSON artifacts describing dataset metadata, column-level aggregate evidence, trace metadata, a local `test_suggestion_payload.json` artifact for future candidate-generation work, and optional candidate validation artifacts.

This version still does **not** generate candidate tests, call an LLM, execute tests, mark candidates as approved, or produce reports. Candidate JSON files passed with `--candidates` are local human/fixture inputs used to exercise the validation layer before any LLM generation exists. No OpenAI or other LLM dependency is included.

## What is implemented

- a Python package named `data_test_suggestion_agent`
- a CLI command named `data-test-suggestion-agent`
- no-input scaffold trace output
- CSV intake
- XLSX/XLSM intake with optional `--sheet` selection
- optional YAML context loading with `--context`
- dataset metadata capture
- safe aggregate profiling in `dataset_profile.json`
- local safe evidence payload construction in `test_suggestion_payload.json`
- optional manual candidate validation with `--candidates`
- validation artifacts in `validated_test_suggestions.json` and `rejected_test_suggestions.json`
- trace metadata for dataset intake, profiling, context-loading, evidence-payload, candidate-loading, and suggestion-validation stages
- pytest coverage for intake, profiling, context loading, evidence payloads, candidate loading, candidate validation, and CLI behavior

## What is intentionally not implemented yet

This version does not include:

- OpenAI or other LLM calls
- prompt templates
- automatic candidate test generation
- test execution
- approved test output
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

Profile the synthetic customer sample dataset and build the local evidence payload:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --output-dir outputs
```

Profile the synthetic customer sample dataset with human-authored context included in the local evidence payload:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --output-dir outputs
```

Validate manually supplied local candidate suggestions against the dataset, aggregate profile, and optional context:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests.json \
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

A no-input scaffold run creates only:

```text
outputs/data_test_trace.json
```

A dataset profiling run without context or candidates creates:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
```

A dataset profiling run with `--context` and no candidates creates the same three artifacts:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
```

A dataset profiling run with `--candidates` creates five artifacts:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
outputs/validated_test_suggestions.json
outputs/rejected_test_suggestions.json
```

`data_test_trace.json` records the run status, package metadata, artifact paths, stage status, and candidate validation counts when `--candidates` is used. In input mode, `dataset_intake`, `profiling`, and `evidence_payload` are marked `completed`. When `--context` is provided, `context_loading` is marked `completed` and trace metadata records the context path, context file name, optional dataset name, preferred strictness, referenced-field count, and any missing context fields for review. Without `--context`, `context_loading` is marked `not_requested`. With `--candidates`, `candidate_loading` and `suggestion_validation` are marked `completed`; without candidates they are marked `not_requested`. Later stages such as LLM suggestions, test execution, and reporting remain `not_implemented`.

`dataset_profile.json` contains deterministic aggregate evidence such as row count, column count, column names, pandas dtypes, null counts, unique counts, numeric bounds/means, text length statistics, date parse statistics, and cautious deterministic candidate hints. It intentionally avoids raw rows, example values, top values, and distinct value lists. Human-authored context is not written into `dataset_profile.json`; keeping it separate preserves the distinction between deterministic source-data profile evidence and reviewer-authored metadata.

`test_suggestion_payload.json` combines dataset metadata, safe aggregate profile evidence, optional human-authored context summary, and explicit authority/safety boundaries. It is local evidence for future bounded candidate test generation only. In this PR, it is not sent anywhere, no LLM is called, and no candidate tests are generated by the agent. The payload does not contain raw rows, example values, top values, distinct value lists, sampled records, or source data previews.

`validated_test_suggestions.json` contains candidate suggestions that passed the deterministic local contract. These candidates are **not** approved tests, are **not** automatically correct or complete, and are **not** executed. The artifact explicitly records `candidate_tests_generated_by_this_agent: false`, `llm_called: false`, `validated_candidates_are_approved_tests: false`, and `tests_executed: false`.

`rejected_test_suggestions.json` contains candidates rejected by the deterministic contract, with reason codes and messages. Rejection reasons cover schema problems, unsupported test types, invalid severities, invalid `suggested_by` values, missing or unknown columns, parameter-shape problems, profile mismatches, suspicious execution/code fields, raw-row/example-value fields, and unsupported extra fields.

## Manual candidate validation

The optional `--candidates PATH` argument points to a local JSON file with a top-level `candidate_tests` array. The file is not produced by this CLI. It is a manual fixture/input that proves candidate suggestions must pass deterministic validation before any future execution or reviewer workflow.

Allowed candidate test types in this PR are:

- `not_null`
- `unique`
- `accepted_values`
- `numeric_range`
- `date_parseable`
- `date_not_future`
- `regex_match`

Adding these names to the contract does not mean tests are executed. Parameter validation is shape-only and deterministic. For example, `accepted_values.allowed_values` must be supplied by the candidate file and is never inferred from raw source data in this PR; `regex_match.pattern` must compile, but it is not run against dataset rows.

## Optional YAML context

A context file lets a human reviewer describe dataset meaning that deterministic profiling cannot infer reliably, such as expected grain, important fields, known ID/date/categorical fields, business caveats, fields to ignore, and preferred strictness. Context can add validation notes or reject candidates for fields marked to ignore, but context is not required and does not make any candidate approved.

If `preferred_strictness` is omitted from context YAML, the loader defaults it to `cautious`. Allowed values are `cautious`, `standard`, and `strict`. Fields referenced by context are checked against the loaded dataset columns. Missing references are recorded as `missing_context_fields` warnings in `data_test_trace.json` and `test_suggestion_payload.json` instead of failing the run, because they may reflect stale context, renamed columns, or a subset extract rather than a dataset defect.

Expected clean user errors include:

- `--context` requires `--input` so context can be checked against dataset columns.
- `--candidates` requires `--input` so candidates can be validated against dataset columns.
- `--sheet` requires `--input`.
- `--sheet` is only valid for Excel inputs (`.xlsx` or `.xlsm`).
- malformed or incorrectly shaped candidate JSON fails without a long traceback and without writing validation artifacts.

## Authority boundary

This project is designed around deterministic evidence and human review. Future versions may generate candidate tests, but those candidates should be treated as suggestions for review. Validated candidates in this PR have only passed a local safety/schema/profile/context gate; they are not approved tests, are not executed, and do not imply complete or correct coverage.

The current implementation does not send raw rows to any model, does not call an LLM, does not execute arbitrary code, does not generate candidate tests, and does not make legal, privacy, or compliance verdicts.
