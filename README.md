# Data Test Suggestion Agent

A local-first Python CLI agent for reviewable data test suggestion workflows.

The project helps answer:

> What data tests should we add for this dataset?

The workflow combines deterministic evidence collection, optional human-authored context, optional bounded LLM candidate generation, deterministic validation, optional deterministic execution, and human review. LLM-generated candidates are suggestions only; they are never approved tests and never authoritative.

## Current status

The project supports:

- deterministic CSV/XLSX/XLSM dataset intake
- safe aggregate profiling in `dataset_profile.json`
- optional human-authored YAML context loading with `--context`
- local safe evidence payload construction in `test_suggestion_payload.json`
- optional manual candidate validation with `--candidates`
- optional OpenAI-backed candidate generation with `--generate-candidates`
- deterministic validation of all manual or generated candidates
- optional deterministic local execution of validated candidates with `--execute-candidates`

The LLM role is the heavier but bounded role: it can propose structured candidate test JSON from `test_suggestion_payload.json`-style safe evidence only. It does not see raw dataset rows, source files, sampled records, top values, distinct value lists, execution rows, API keys, or local source previews. Generated candidates are immediately passed through deterministic validation and may be rejected. Execution remains optional, deterministic, local-only, aggregate-only, and limited to validated candidates.

## Install

Base deterministic usage, tests, and CI use no OpenAI dependency:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional LLM generation requires the `llm` extra:

```bash
pip install -e ".[dev,llm]"
```

Run tests:

```bash
pytest
```

## CLI examples

Show help and version:

```bash
data-test-suggestion-agent --help
data-test-suggestion-agent --version
```

Run no-input scaffold mode:

```bash
data-test-suggestion-agent --output-dir outputs
```

Profile the sample dataset and build safe evidence:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --output-dir outputs
```

Include human-authored context:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --output-dir outputs
```

Validate manually supplied local candidates:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests.json \
  --output-dir outputs
```

Execute only manually supplied candidates that passed deterministic validation:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests.json \
  --execute-candidates \
  --output-dir outputs
```

Generate bounded LLM candidate suggestions from safe evidence only:

```bash
export OPENAI_API_KEY="..."
export DATA_TEST_AGENT_LLM_MODEL="your-model-name"

data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --output-dir outputs
```

Generate candidates and then execute only those that passed deterministic validation:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --execute-candidates \
  --output-dir outputs
```

Profile an Excel workbook and select a sheet explicitly:

```bash
data-test-suggestion-agent \
  --input path/to/workbook.xlsx \
  --sheet Customers \
  --output-dir outputs
```

## LLM configuration

`--generate-candidates` is optional. When used, the model is resolved from:

1. `--llm-model MODEL_NAME`
2. `DATA_TEST_AGENT_LLM_MODEL`

`OPENAI_API_KEY` must be present in the environment. The CLI does not print or write the API key. If the model, API key, or optional OpenAI SDK dependency is missing, the CLI fails cleanly without a long traceback and without writing LLM/validation/execution artifacts.

`--generate-candidates` and `--candidates` are mutually exclusive: use either manual candidate input or LLM candidate generation, not both.

## Expected output artifacts

A no-input scaffold run creates only:

```text
outputs/data_test_trace.json
```

A profiling run without candidates creates:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
```

A manual candidate validation run creates:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
outputs/validated_test_suggestions.json
outputs/rejected_test_suggestions.json
```

An LLM candidate generation run creates:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
outputs/llm_candidate_tests.json
outputs/validated_test_suggestions.json
outputs/rejected_test_suggestions.json
```

Any validation run with `--execute-candidates` also creates:

```text
outputs/test_execution_results.json
```

## Artifact meanings

`dataset_profile.json` contains deterministic aggregate evidence such as row count, column count, column names, dtypes, null counts, unique counts, numeric bounds/means, text length statistics, and date parse statistics. It intentionally avoids raw rows, example values, top values, distinct value lists, sampled records, and source previews.

`test_suggestion_payload.json` combines aggregate profile evidence, optional human-authored context summary, and explicit safety/authority boundaries. This is the only dataset-derived evidence sent to the LLM when `--generate-candidates` is used. It records that raw rows, example values, top values, and distinct value lists are not included.

`llm_candidate_tests.json` is written only after successful LLM generation and parsing. It records safe metadata such as model, max candidates, source payload artifact, `llm_called: true`, `candidate_tests_generated_by_this_agent: true`, and parsed `candidate_tests`. It does not write raw OpenAI responses, prompts, chain-of-thought, raw rows, examples, top values, or distinct value lists.

`validated_test_suggestions.json` contains candidates that passed deterministic validation. These candidates are **not** approved tests and are **not** complete or automatically correct coverage. Manual mode records `candidate_tests_generated_by_this_agent: false` and `llm_called: false`; LLM mode records both as `true`.

`rejected_test_suggestions.json` contains candidates rejected by deterministic validation, with reason codes and messages. Generated candidates may be rejected for unsupported types, unknown columns, unsafe fields, parameter-shape problems, profile/context incompatibility, or other deterministic rules.

`test_execution_results.json` is written only with `--execute-candidates`. It executes validated candidates with fixed local pandas/Python logic for supported test types. Rejected candidates are not executed. Failed checks are data-quality outcomes and do not make the CLI exit non-zero. Execution results are not approved tests and contain aggregate counts only.

## Candidate validation contract

Allowed candidate test types are:

- `not_null`
- `unique`
- `accepted_values`
- `numeric_range`
- `date_parseable`
- `date_not_future`
- `regex_match`

Allowed severities are `low`, `medium`, and `high`. Candidate objects use this shape:

```json
{
  "test_id": "customer_id_unique",
  "test_type": "unique",
  "column": "customer_id",
  "severity": "high",
  "parameters": {},
  "rationale": "Reason based on safe evidence or human context.",
  "suggested_by": "manual_fixture or llm_candidate"
}
```

For LLM generation, the prompt and structured output schema require `suggested_by: "llm_candidate"`, supported test types only, and a top-level `{ "candidate_tests": [...] }` object. The deterministic validator remains authoritative for schema validation, supported test types, dataset column checks, profile compatibility checks, context checks, and safe parameter rules.

## Optional YAML context

A context file lets a human reviewer describe dataset meaning that deterministic profiling cannot infer reliably, such as expected grain, important fields, known ID/date/categorical fields, business caveats, fields to ignore, and preferred strictness. Context can add validation notes or reject candidates for fields marked to ignore, but context is not required and does not make any candidate approved.

If `preferred_strictness` is omitted, the loader defaults it to `cautious`. Allowed values are `cautious`, `standard`, and `strict`. Fields referenced by context are checked against loaded dataset columns. Missing references are recorded as warnings in `data_test_trace.json` and `test_suggestion_payload.json` rather than failing the run.

## Clean user errors

Expected clean failures include:

- `--context` requires `--input`.
- `--candidates` requires `--input`.
- `--generate-candidates` requires `--input`.
- `--sheet` requires `--input` and is only valid for Excel inputs.
- `--execute-candidates` requires either `--candidates` or `--generate-candidates` with `--input`.
- `--generate-candidates` and `--candidates` cannot be used together.
- `--generate-candidates` requires a resolved model and `OPENAI_API_KEY`.
- OpenAI SDK/API errors fail cleanly without long tracebacks.
- malformed candidate JSON or malformed LLM output fails without validation/execution artifacts.

## Authority boundary

The LLM may propose candidate tests, but it is not authoritative. It must not see raw rows, source files, or API keys; generate executable code; approve tests; claim coverage is complete; make legal/compliance/privacy verdicts; or bypass deterministic validation or execution rules.

Deterministic code remains authoritative for schema validation, supported test types, dataset column checks, profile compatibility checks, context checks, artifact writing, trace status, and local execution of validated candidates. A human reviewer decides what becomes official.
