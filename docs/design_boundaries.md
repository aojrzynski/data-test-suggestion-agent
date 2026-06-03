# Design boundaries

The central safety model is simple:

```text
LLM proposes → deterministic code validates and optionally executes → human decides
```

The project is intentionally not an approval system. It is a local-first assistant for producing reviewable evidence, candidate tests, validation results, aggregate execution outcomes, and a human review report.

## LLM proposes

When enabled, the LLM receives safe aggregate evidence and optional human-authored context. It can propose structured candidate tests, but those suggestions are not authoritative.

The LLM cannot:

- approve tests;
- claim that coverage is complete;
- bypass deterministic validation;
- execute checks;
- generate code that the agent runs;
- make legal, compliance, or privacy verdicts.

## Deterministic code validates

Manual and LLM-generated candidates pass through the same deterministic validator. Validation checks whether a candidate fits the supported contract and whether it is safe enough for review and optional local execution.

Validation is a safety gate, not approval. A candidate that passes validation can still be wrong, too strict, too weak, duplicated, or inappropriate for production.

## Human decides

A human reviewer decides which suggestions, if any, should become official tests in the team's actual data quality framework. The agent does not write an approved test suite, does not create `suggested_tests.yaml`, and does not mark candidates as accepted for production use.

## No raw rows to the LLM

The safe evidence payload is built from aggregate profile evidence and optional human-authored context. It intentionally excludes raw rows, sampled records, source previews, example values, top values, and distinct value lists.

This boundary keeps the optional model call focused on high-level evidence rather than row-level data.

## No row-level failure exports

Execution results are aggregate-only. They can report that a check passed or failed and provide counts, but they do not export raw failing rows or raw failing values.

This keeps review artifacts useful without turning the tool into a row-level data export path.

## No arbitrary generated code execution

Candidate tests are data-only suggestions. The validator rejects suspicious executable fields such as code, SQL, expressions, scripts, commands, or function bodies. The executor only runs fixed local logic for supported test types.

This means the LLM or a candidate JSON file cannot smuggle executable behavior into the runtime path.

## No legal, compliance, or privacy verdicts

The agent can help identify candidate data quality checks. It does not determine whether a dataset is legally compliant, privacy-safe, contractually acceptable, regulated, or production-ready.

Those decisions require human governance outside this tool.

## No automatic approval

Validated candidates and executed checks are still review materials. The report repeats this boundary because it is easy to misread a passing check as an approved production test. Passing validation or execution does not create official coverage.

## Why `accepted_values` are not inferred from raw distinct values

Accepted value tests are powerful but risky. Inferring allowed values directly from raw distinct values can accidentally freeze historical mistakes, leak sensitive categories, or treat incomplete data as business truth.

This project requires `accepted_values` candidates to come from a supplied candidate or generated structured suggestion that survives validation. The workflow is designed so a human reviewer can evaluate whether the proposed set reflects business rules, not merely what happened to appear in the current file.

## Why rejected candidates can still be useful

Rejected candidates are not thrown away silently. They are written with reason codes because rejections can reveal useful information:

- an LLM suggested an unsupported test type;
- a candidate referenced an unknown column;
- a field was marked to ignore in context;
- a parameter shape was unsafe or incomplete;
- a suggestion tried to include row-level evidence or executable text.

These rejected ideas can help a reviewer improve context, rewrite a candidate manually, or understand where generated suggestions exceeded the tool's boundaries.

## Why failed execution checks are review outcomes, not process failures

A failed candidate check usually means the data did not satisfy the proposed rule. That is useful review information, not necessarily a CLI failure.

For example, a `not_null` candidate can execute successfully and report failures because nulls exist. The process worked: the validated check ran locally and produced an aggregate outcome for human review. The human reviewer then decides whether the candidate should become an official test, be adjusted, or be discarded.
