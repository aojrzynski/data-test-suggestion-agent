# Architecture

Data Test Suggestion Agent is a local-first CLI workflow. It separates deterministic data handling from optional LLM brainstorming so candidate tests can be reviewed without treating generated text as authoritative.

## Module overview

- `src/data_test_suggestion_agent/cli.py` coordinates command-line parsing, user-facing error handling, stage ordering, artifact writing, optional LLM generation, optional execution, and optional report generation.
- `src/data_test_suggestion_agent/intake.py` loads local CSV, XLSX, and XLSM files and records dataset metadata.
- `src/data_test_suggestion_agent/profiling.py` builds safe aggregate profiles using pandas. The profile intentionally avoids raw rows, sample records, top values, and distinct value lists.
- `src/data_test_suggestion_agent/models.py` defines typed dataset metadata and profile models.
- `src/data_test_suggestion_agent/context_loader.py` loads optional human-authored YAML context and validates references against loaded dataset columns when a dataset is available.
- `src/data_test_suggestion_agent/evidence_payload.py` builds the safe evidence payload that can be reviewed locally or sent to the optional LLM generation path.
- `src/data_test_suggestion_agent/candidate_models.py` defines the narrow candidate test contract, allowed test types, allowed severities, and fields that are rejected because they look like executable code or row-level leakage.
- `src/data_test_suggestion_agent/candidate_loader.py` loads manually supplied local candidate JSON.
- `src/data_test_suggestion_agent/llm_prompt_builder.py`, `src/data_test_suggestion_agent/llm_schema.py`, and `src/data_test_suggestion_agent/llm_candidate_generator.py` contain the optional OpenAI-backed candidate generation path.
- `src/data_test_suggestion_agent/candidate_validator.py` deterministically validates manual or generated candidates.
- `src/data_test_suggestion_agent/test_executor.py` deterministically executes only validated candidates with fixed local logic.
- `src/data_test_suggestion_agent/report_generator.py` builds the deterministic Markdown human review report.
- `src/data_test_suggestion_agent/output_writers.py` writes deterministic JSON and Markdown artifacts.

## Data flow

```text
local dataset
  + optional human-authored YAML context
  ↓
intake and aggregate profiling
  ↓
dataset_profile.json
  ↓
safe evidence payload
  ↓
test_suggestion_payload.json
  ↓
manual candidates OR optional LLM-generated candidates
  ↓
deterministic validation
  ↓
validated_test_suggestions.json + rejected_test_suggestions.json
  ↓
optional deterministic local execution of validated candidates
  ↓
test_execution_results.json
  ↓
optional deterministic human review report
  ↓
test_suggestion_report.md
```

The no-input path writes only a trace artifact. Input-mode paths produce a profile and safe evidence payload. Candidate paths add validation artifacts. Execution and reporting are opt-in.

## Where deterministic logic happens

Most of the project is deterministic:

- dataset file loading and metadata capture;
- aggregate profiling;
- YAML context parsing and context reference checks;
- safe evidence payload construction;
- manual candidate loading;
- candidate schema and safety validation;
- local execution of supported validated candidate types;
- JSON artifact writing with sorted keys;
- Markdown report generation.

This means the same input files and command options should produce stable local artifacts, aside from expected file-system paths and any future intentionally variable metadata.

## Where LLM logic happens

LLM logic is isolated to the optional generation path. When `--generate-candidates` is used, the CLI sends the safe evidence payload, not raw dataset rows, to the OpenAI-backed generator. The generator requests structured candidate test output and writes parsed candidate suggestions to `llm_candidate_tests.json` only after successful generation and parsing.

The LLM does not execute checks, approve tests, bypass validation, create official test coverage, or write the human review report.

## Why the LLM is optional

The core workflow is useful without an LLM: a user can profile a dataset, add human-authored context, validate manually supplied candidates, execute validated checks, and write a review report. Keeping generation optional supports deterministic demos, local development, CI, and environments where an external API call is not desired.

The optional LLM path is for brainstorming candidate tests from safe aggregate evidence. It is not required for validation, execution, or reporting.

## Why OpenAI is an optional dependency

OpenAI support is behind the `llm` extra dependency so the base install remains focused on deterministic local behavior. Users who only need profiling, validation, execution, and reporting can install `pip install -e ".[dev]"`. Users who want LLM candidate generation can install `pip install -e ".[dev,llm]"` and provide `OPENAI_API_KEY` plus a model name.

This keeps CI and deterministic portfolio demos simple while still showing how an external model can be integrated behind a narrow boundary.

## Why validation sits after generation

Generation can come from a human-authored JSON file or from the optional LLM path. In both cases, validation is the safety gate that decides whether a candidate is well-formed enough for review and optional execution.

Validation checks the allowed candidate shape, supported test type, severity, column reference, parameter shape, profile compatibility, context boundaries, suspicious executable fields, and row-leakage fields. This prevents generated text from becoming runtime behavior or approval by default.

## Why execution only runs validated candidates

Execution is intentionally downstream of validation. The executor does not interpret arbitrary code supplied by a candidate. It only runs fixed local logic for supported candidate types that passed deterministic validation.

Rejected candidates are not executed. This keeps execution bounded, repeatable, and aggregate-only.

## Why report generation is deterministic

The report is assembled from in-memory artifacts already produced during the run: profile evidence, context summary, validation results, optional execution results, and artifact paths. It does not call an LLM and does not use a Markdown rendering dependency.

The report is designed as human review material. It repeats the authority boundary so readers do not mistake candidate suggestions or execution outcomes for approved tests or complete coverage.
