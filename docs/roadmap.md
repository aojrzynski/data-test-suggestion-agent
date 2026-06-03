# Roadmap

## Current version

The current version supports a local-first review workflow for CSV, XLSX, and XLSM datasets:

- local dataset intake;
- safe aggregate profiling;
- optional human-authored YAML context;
- safe evidence payload creation with no raw rows;
- optional bounded OpenAI candidate generation;
- deterministic validation for manual or generated candidates;
- optional validated-only local execution;
- deterministic JSON artifacts and Markdown review report.

## Possible future improvements

- Export human-reviewed candidates to dbt tests.
- Export human-reviewed candidates to Great Expectations.
- Add richer candidate test types.
- Add database connectors.
- Expand the context schema for richer business rules and ownership notes.
- Improve Excel sheet discovery and workbook metadata reporting.
- Add configurable report sections.
- Add a non-OpenAI LLM adapter behind the same bounded generation contract.
- Add optional row-level failure export with explicit user opt-in and safeguards.

## Not currently planned

- Automatic approval.
- Raw row upload to an LLM.
- Arbitrary generated code execution.
- Legal, compliance, or privacy verdicts.
- Replacing human review.
