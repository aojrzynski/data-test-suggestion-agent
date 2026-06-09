# Data Test Suggestion Agent

Data Test Suggestion Agent helps answer a practical question:

> What data tests should we add for this dataset?

It looks at a local CSV or Excel dataset, builds safe profile evidence, optionally uses human-authored context and an LLM to suggest candidate tests, validates those candidates with deterministic code, optionally runs validated checks locally, and writes a review report for a human reviewer.

> [!NOTE]
> **Part of the Data Agent Suite.**
> 
> This repo is one of 10 local-first data/AI agents built around practical data workflows, deterministic evidence, bounded LLM use, and review-ready artifacts.
> 
> The full ordered list of agents is included near the bottom of this README.
> 
> See the full suite overview: [Data Agent Suite](https://aojrzynski.github.io/agents/)

## The problem

Data teams often know a dataset needs tests, but they may not know where to start. A raw profile can show useful facts such as null counts, unique counts, inferred types, numeric ranges, and date parsing signals. Those facts are helpful, but they do not explain the business meaning of the data.

Context matters. A nullable column might be acceptable in one dataset and a serious quality issue in another. A low-cardinality field might need an accepted-values check if it drives reporting, or it might be unimportant if it is only a temporary label.

LLMs can help suggest ideas, but they should not be trusted blindly. Reviewers need traceable evidence, structured candidate tests, deterministic validation results, optional execution outcomes, and human judgment before anything becomes an official data test.

## What this project does

The tool:

- loads local CSV, XLSX, and XLSM datasets;
- profiles the dataset with safe aggregate summaries;
- optionally loads human-authored YAML context;
- builds a safe evidence payload with no raw rows;
- optionally asks an LLM to propose structured candidate tests from safe evidence only;
- validates manual or LLM-generated candidates deterministically;
- optionally executes only validated candidates locally;
- writes traceable JSON artifacts and a Markdown review report.

The deterministic workflow is the default path and does not require an API key.

## Why deterministic evidence matters

Data test suggestions should be inspectable and repeatable. Given the same input dataset, context, candidate file, and command options, the deterministic profile, evidence payload, validation artifacts, execution results, and report should tell the same story.

That matters because reviewers need to see why a candidate passed validation, why another candidate was rejected, and what happened when a validated check ran locally. LLM output can be useful for suggesting ideas, but it should not replace deterministic evidence.

## Why not just ask an LLM?

An LLM might invent columns or business rules. It might suggest tests that do not match the dataset. It might produce vague advice instead of structured candidates. Raw dataset rows should not be casually pasted into an LLM, and an LLM should not write or execute arbitrary code. It also should not approve tests, claim coverage is complete, or make legal, compliance, or privacy verdicts.

This project splits the work into bounded stages:

- deterministic code profiles the dataset and builds safe evidence;
- optional LLM generation receives only the safe evidence payload;
- the LLM can propose structured candidate tests;
- deterministic validation checks candidate shape, supported types, columns, parameters, profile compatibility, and safety boundaries;
- deterministic execution only runs validated candidates with fixed local logic;
- a human reviewer makes final decisions.

The LLM is not decorative. It is allowed to propose candidate tests from safe evidence. It is bounded, non-authoritative, and always followed by deterministic validation.

## Why this is an agent

This is an agent because it orchestrates a multi-step workflow:

```text
intake -> profile -> context -> evidence payload -> optional LLM candidates -> validation -> optional execution -> report
```

It does not perform open-ended autonomy. It runs a bounded workflow, keeps each stage traceable, and produces artifacts for a human reviewer. The optional LLM stage is active because it can generate candidate test suggestions, but it is non-authoritative.

## Quick start

Install the base deterministic workflow and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest -q
```

Optional LLM candidate generation requires the LLM extra:

```bash
python -m pip install -e ".[dev,llm]"
```

`OPENAI_API_KEY` is not needed for deterministic runs. It is only needed when `--generate-candidates` is requested.

## Example commands

Recommended deterministic demo:

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests_with_rejections.json \
  --execute-candidates \
  --write-report \
  --output-dir outputs/customer_test_review
```

Optional LLM generation demo:

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --execute-candidates \
  --write-report \
  --output-dir outputs/customer_test_review_llm
```

Excel example with an explicit sheet:

```bash
python -m data_test_suggestion_agent.cli \
  --input path/to/workbook.xlsx \
  --sheet Sheet1 \
  --context config/examples/customer_dataset_context.yaml \
  --output-dir outputs/excel_profile
```

The Excel command assumes the workbook exists locally. More copy-paste examples are in [`docs/example_commands.md`](docs/example_commands.md).

## Output artifacts

Depending on the command options, the tool can write:

- `data_test_trace.json`
- `dataset_profile.json`
- `test_suggestion_payload.json`
- `llm_candidate_tests.json`
- `validated_test_suggestions.json`
- `rejected_test_suggestions.json`
- `test_execution_results.json`
- `test_suggestion_report.md`

The artifacts are designed to support review without storing raw dataset rows, raw failing rows, source previews, top values, or distinct value lists. See [`docs/artifacts.md`](docs/artifacts.md) for detailed artifact explanations.

## Authority boundary

- Deterministic outputs provide evidence, validation, and execution results.
- LLM-generated candidates are suggestions, not decisions.
- Candidate validation is a safety gate, not approval.
- Execution results are aggregate outcomes, not official test coverage.
- No raw rows are sent to the LLM.
- No arbitrary candidate-provided code is executed.
- The tool does not provide legal, compliance, or privacy verdicts.
- A human reviewer decides what becomes official.

## Project structure

- `src/data_test_suggestion_agent/cli.py`: command-line orchestration and user-facing errors.
- `src/data_test_suggestion_agent/intake.py`: local CSV, XLSX, and XLSM intake.
- `src/data_test_suggestion_agent/profiling.py`: aggregate dataset profiling.
- `src/data_test_suggestion_agent/context_loader.py`: optional YAML context loading.
- `src/data_test_suggestion_agent/evidence_payload.py`: safe evidence payload construction.
- `src/data_test_suggestion_agent/candidate_models.py`: supported candidate test contract.
- `src/data_test_suggestion_agent/candidate_loader.py`: manual candidate JSON loading.
- `src/data_test_suggestion_agent/candidate_validator.py`: deterministic candidate validation.
- `src/data_test_suggestion_agent/llm_prompt_builder.py`, `src/data_test_suggestion_agent/llm_schema.py`, `src/data_test_suggestion_agent/llm_candidate_generator.py`: optional bounded LLM candidate generation.
- `src/data_test_suggestion_agent/test_executor.py`: validated-only local execution.
- `src/data_test_suggestion_agent/report_generator.py`: deterministic Markdown report generation.
- `src/data_test_suggestion_agent/output_writers.py`: deterministic artifact writing.
- `config/examples/`: example context and candidate files.
- `sample_data/`: local sample datasets.
- `docs/`: deeper architecture, design, artifact, command, demo, and roadmap notes.

## Limitations and non-goals

- Not a legal, compliance, or privacy decision tool.
- Not a replacement for human review.
- Not a raw-data LLM upload tool.
- Does not generate approved production test suites.
- Does not create `suggested_tests.yaml`.
- No database connectors yet.
- Limited to CSV, XLSX, and XLSM files.
- Limited candidate test types.
- LLM quality depends on safe evidence, context, model behavior, and prompt adherence.

## Further reading

- [`docs/architecture.md`](docs/architecture.md): module responsibilities, data flow, and deterministic/LLM boundaries.
- [`docs/design_principles.md`](docs/design_principles.md): design principles and authority boundaries.
- [`docs/artifacts.md`](docs/artifacts.md): artifact-by-artifact review guide.
- [`docs/demo_workflow.md`](docs/demo_workflow.md): local end-to-end demo workflow.
- [`docs/example_commands.md`](docs/example_commands.md): additional copy-paste commands.
- [`docs/roadmap.md`](docs/roadmap.md): current scope and possible future improvements.

---

> [!NOTE]
> **Data Agent Suite**  
> This repo is part of the **Data Agent Suite**: 10 local-first data/AI agents focused on practical data workflows, deterministic evidence, bounded LLM use, and review-ready artifacts.
> 
> See the full suite overview: [Data Agent Suite](https://aojrzynski.github.io/agents/)
>
> 1. [Data Quality Triage Agent](https://github.com/aojrzynski/data-quality-triage-agent)
> 2. [Data Reconciliation Agent](https://github.com/aojrzynski/data-reconciliation-agent)
> 3. [Data Dictionary Agent](https://github.com/aojrzynski/data-dictionary-agent)
> 4. [Data Contract Review Agent](https://github.com/aojrzynski/data-contract-review-agent)
> 5. [Sensitive Field Review Agent](https://github.com/aojrzynski/sensitive-field-review-agent)
> 6. **Data Test Suggestion Agent**
> 7. [Dataset Onboarding Reviewer Workflow](https://github.com/aojrzynski/dataset-onboarding-reviewer-workflow)
> 8. [Data Quality Investigation Workflow](https://github.com/aojrzynski/data-quality-investigation-workflow)
> 9. [Project Evidence Review Agent](https://github.com/aojrzynski/project-evidence-review-agent)
> 10. [Data Migration Readiness Review Agent](https://github.com/aojrzynski/data-migration-readiness-review-agent)
