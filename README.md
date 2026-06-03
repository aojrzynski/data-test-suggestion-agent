# Data Test Suggestion Agent

Data Test Suggestion Agent is a local-first Python CLI agent that profiles a dataset, builds safe aggregate evidence, optionally uses an LLM to propose candidate data tests, validates those candidates deterministically, optionally executes validated checks, and writes a human-readible review report.

It helps answer one practical question:

> What data tests should we add for this dataset?

The answer is intentionally reviewable. Candidate tests are suggestions, not approved tests, and the project keeps deterministic validation, local execution, and human judgment separate from optional LLM generation.

## Why this exists

Data teams often know a dataset needs tests, but the first step can be unclear. A raw profile can show null counts, unique counts, types, numeric ranges, and date parsing signals, but it does not know which columns are business-critical or which assumptions should become checks.

LLMs can help brainstorm useful test ideas, especially when they receive both aggregate profile evidence and human-authored dataset context. They should not be trusted as authorities, though. This project demonstrates a safer pattern:

- the LLM proposes candidate tests from safe evidence only;
- deterministic code validates candidate shape, supported types, columns, parameters, and context boundaries;
- deterministic code optionally executes only validated checks locally;
- a human reviewer decides what, if anything, becomes official test coverage.

## How it works

```text
dataset + optional context
→ safe profile
→ safe evidence payload
→ optional LLM candidate generation
→ deterministic validation
→ optional deterministic execution
→ human review report
```

At a high level, the agent:

1. Deterministically loads a local CSV, XLSX, or XLSM dataset.
2. Builds an aggregate-only profile with no raw rows, samples, top values, or distinct value lists.
3. Optionally loads human-authored YAML context that explains dataset meaning.
4. Builds a safe evidence payload suitable for review or optional LLM input.
5. Optionally asks an OpenAI model to return structured candidate tests from that safe payload only.
6. Deterministically validates manual or LLM-generated candidate tests.
7. Optionally executes only validated candidates with fixed local logic.
8. Writes deterministic JSON artifacts and, when requested, a Markdown report for human review.

## Install

Base deterministic usage, tests, and CI do not require the OpenAI dependency:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
```

## Quick deterministic demo

This recommended demo uses the sample customer dataset, sample human-authored context, a mixed candidate fixture with both accepted and rejected candidates, deterministic local execution, and a deterministic review report:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests_with_rejections.json \
  --execute-candidates \
  --write-report \
  --output-dir outputs
```

Generated artifacts:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/test_suggestion_payload.json
outputs/validated_test_suggestions.json
outputs/rejected_test_suggestions.json
outputs/test_execution_results.json
outputs/test_suggestion_report.md
```

Open `outputs/test_suggestion_report.md` first if you want the most readable review artifact. Then inspect the JSON files for the deterministic evidence, validation results, rejected candidates, and aggregate execution outcomes behind the report.

## Optional LLM demo

LLM candidate generation is optional. It requires the OpenAI extra dependency, an API key, and a model name supplied through either `DATA_TEST_AGENT_LLM_MODEL` or `--llm-model`.

Install with the LLM extra:

```bash
pip install -e ".[dev,llm]"
```

Set configuration:

```bash
export OPENAI_API_KEY="..."
export DATA_TEST_AGENT_LLM_MODEL="your-model-name"
```

PowerShell equivalent:

```powershell
$env:OPENAI_API_KEY = "..."
$env:DATA_TEST_AGENT_LLM_MODEL = "your-model-name"
```

Run optional generation, deterministic validation, deterministic execution, and report writing:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --execute-candidates \
  --write-report \
  --output-dir outputs
```

You can also pass the model explicitly:

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --llm-model your-model-name \
  --output-dir outputs
```

`--generate-candidates` and `--candidates` are mutually exclusive. Use manual candidate input for deterministic demos and optional LLM generation when you want to exercise the bounded generation path.

## Key design boundaries

- No raw rows are sent to the LLM.
- No sampled records, source previews, top values, distinct value lists, raw failing rows, or raw failing values are written to artifacts or reports.
- No arbitrary candidate-provided code is executed.
- Candidate validation and execution are deterministic safety gates, not approval.
- The agent does not auto-approve tests or create an official test suite.
- The report is human review material, not a coverage certificate.
- No legal, compliance, or privacy verdicts are made.
- A human reviewer decides what becomes official.

## Artifact overview

| Artifact | Written when | Purpose |
| --- | --- | --- |
| `data_test_trace.json` | every run | Run status, stage status, and artifact path summary. |
| `dataset_profile.json` | input-mode runs | Safe aggregate dataset profile. |
| `test_suggestion_payload.json` | input-mode runs | Aggregate evidence plus optional context and authority boundaries. |
| `llm_candidate_tests.json` | successful `--generate-candidates` runs | Parsed structured LLM candidate suggestions and safe generation metadata. |
| `validated_test_suggestions.json` | manual or LLM candidate runs | Candidate tests that passed deterministic validation, still unapproved. |
| `rejected_test_suggestions.json` | manual or LLM candidate runs | Candidate tests rejected by deterministic validation, with reason codes. |
| `test_execution_results.json` | candidate runs with `--execute-candidates` | Aggregate local execution outcomes for validated candidates only. |
| `test_suggestion_report.md` | input-mode runs with `--write-report` | Deterministic Markdown report for human review. |

See [`docs/artifacts.md`](docs/artifacts.md) for a fuller explanation of what each artifact contains and intentionally omits.

## Candidate validation contract

Allowed candidate test types:

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
  "suggested_by": "manual_fixture"
}
```

Validation checks the candidate contract, supported test types, suspicious executable fields, row-leakage fields, dataset column references, profile compatibility, context boundaries such as fields to ignore, and safe parameter shapes. Passing validation means the candidate is acceptable for review and optional local execution; it does not mean the candidate is approved, correct, complete, or ready for production.

## What this demonstrates

For portfolio reviewers, this project demonstrates:

- Python CLI design with a small, understandable command surface.
- Typed models and dataclasses for dataset profiles, context, candidates, validation results, and execution results.
- pandas-based dataset intake and aggregate profiling.
- Safe JSON artifact design for reviewable agent workflows.
- YAML context loading for human-authored business meaning.
- Optional OpenAI integration behind an `llm` extra dependency.
- Structured LLM output constrained to candidate test suggestions.
- Deterministic validation and deterministic local execution as safety gates.
- Markdown report generation without making approval or coverage claims.
- pytest coverage and GitHub Actions-friendly commands.
- Agent product thinking: bounded autonomy, safe evidence, deterministic controls, and explicit human authority.

## Current limitations

- Input support is limited to local CSV, XLSX, and XLSM files.
- Candidate execution supports a small set of test types.
- There are no database connections.
- There is no dbt or Great Expectations export yet.
- The agent does not generate an approved test suite or `suggested_tests.yaml`.
- The agent does not implement an approval workflow.
- LLM quality depends on the safe evidence payload, supplied context, model behavior, and prompt adherence.
- Generated candidates must be reviewed before any team treats them as official tests.

## More documentation

- [`docs/architecture.md`](docs/architecture.md): module overview, data flow, deterministic logic, and optional LLM boundary.
- [`docs/demo_workflow.md`](docs/demo_workflow.md): copy-paste walkthrough for installing, testing, running demos, inspecting artifacts, and cleaning outputs.
- [`docs/artifacts.md`](docs/artifacts.md): detailed artifact-by-artifact explanations.
- [`docs/design_boundaries.md`](docs/design_boundaries.md): safety and authority model.
- [`docs/portfolio_summary.md`](docs/portfolio_summary.md): concise project summary for technical and semi-technical reviewers.
