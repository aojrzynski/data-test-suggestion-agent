# Architecture

Data Test Suggestion Agent is a local-first CLI workflow for turning a local dataset into reviewable data-test suggestions. It separates deterministic data handling from optional LLM candidate generation so generated text is never treated as authority.

## Module responsibilities

- `src/data_test_suggestion_agent/cli.py` coordinates command-line parsing, user-facing errors, stage ordering, artifact writing, optional LLM generation, optional execution, and optional report generation.
- `src/data_test_suggestion_agent/intake.py` loads local CSV, XLSX, and XLSM files and records dataset metadata.
- `src/data_test_suggestion_agent/profiling.py` builds safe aggregate profiles with pandas. It avoids raw rows, sample records, source previews, top values, and distinct value lists.
- `src/data_test_suggestion_agent/models.py` defines typed dataset metadata and profile models.
- `src/data_test_suggestion_agent/context_loader.py` loads optional human-authored YAML context and validates column references when a dataset is available.
- `src/data_test_suggestion_agent/evidence_payload.py` builds the safe evidence payload used for local review and optional LLM candidate generation.
- `src/data_test_suggestion_agent/candidate_models.py` defines the supported candidate test contract, allowed severities, and fields rejected as executable-code or row-level leakage risks.
- `src/data_test_suggestion_agent/candidate_loader.py` loads manually supplied local candidate JSON.
- `src/data_test_suggestion_agent/llm_prompt_builder.py`, `src/data_test_suggestion_agent/llm_schema.py`, and `src/data_test_suggestion_agent/llm_candidate_generator.py` contain the optional OpenAI-backed candidate generation path.
- `src/data_test_suggestion_agent/candidate_validator.py` deterministically validates manual or generated candidates.
- `src/data_test_suggestion_agent/test_executor.py` executes only validated candidates with fixed local logic.
- `src/data_test_suggestion_agent/report_generator.py` builds the deterministic Markdown report for human review.
- `src/data_test_suggestion_agent/output_writers.py` writes deterministic JSON and Markdown artifacts.

## Data flow

```text
local CSV/XLSX/XLSM dataset
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

A no-input run writes only a trace artifact. Input-mode runs produce a profile and safe evidence payload. Candidate runs add validation artifacts. Execution and report generation are opt-in.

## Deterministic stages

Most stages are deterministic:

- dataset file loading and metadata capture;
- aggregate profiling;
- YAML context parsing and context reference checks;
- safe evidence payload construction;
- manual candidate loading;
- candidate schema and safety validation;
- local execution of supported validated candidate types;
- JSON artifact writing with sorted keys;
- Markdown report generation.

This makes the artifacts inspectable and repeatable for the same input files and command options, aside from expected environment-specific paths and timestamps.

## Optional LLM boundary

LLM logic is isolated to candidate generation. When `--generate-candidates` is used, the CLI sends the safe evidence payload to the OpenAI-backed generator. It does not send raw dataset rows. The generator requests structured candidate test output and writes `llm_candidate_tests.json` only after generation and parsing succeed.

The LLM can propose candidates, but it cannot execute checks, approve tests, bypass validation, create official test coverage, write the report, or make legal, compliance, or privacy verdicts.

## Why OpenAI is optional

The core workflow is useful without a model call: a user can profile a dataset, add human-authored context, validate manually supplied candidates, execute validated checks, and write a report. Keeping OpenAI behind the `llm` extra keeps the base install focused on deterministic local behavior and keeps CI simple.

Users who only need deterministic behavior can install `python -m pip install -e ".[dev]"`. Users who want optional LLM generation can install `python -m pip install -e ".[dev,llm]"` and provide `OPENAI_API_KEY` plus a model name.

## Why validation follows generation

Generation can come from a human-authored JSON file or from the optional LLM path. In both cases, validation is the deterministic gate that decides whether a candidate is well-formed enough for review and optional execution.

Validation checks the allowed candidate shape, supported test type, severity, column references, parameter shape, profile compatibility, context boundaries, suspicious executable fields, and row-leakage fields. This prevents generated text from becoming runtime behavior or approval by default.

## Why execution only runs validated candidates

Execution is intentionally downstream of validation. The executor does not interpret arbitrary code supplied by a candidate. It only runs fixed local logic for supported candidate types that passed deterministic validation.

Rejected candidates are not executed. This keeps execution bounded, repeatable, and aggregate-only.

## Why report generation is deterministic

The report is assembled from artifacts and in-memory results already produced during the run: profile evidence, context summary, validation results, optional execution results, and artifact paths. It does not call an LLM and does not use a Markdown rendering dependency.

The report is human review material. It repeats the authority boundary so readers do not mistake candidate suggestions or execution outcomes for approved tests or complete coverage.
