# Design principles

Data Test Suggestion Agent is built around a conservative workflow:

```text
deterministic evidence -> optional bounded suggestions -> deterministic validation -> optional validated-only execution -> human review
```

The goal is not to approve tests automatically. The goal is to produce useful, traceable review material for deciding which data tests may be worth adding outside this tool.

## Deterministic evidence first

The workflow starts by loading the local dataset and building an aggregate profile with deterministic code. This gives every later stage a concrete evidence base: row counts, column counts, null counts, unique counts, inferred profile types, numeric ranges, text length summaries, empty string counts, and date parsing signals.

The profile is useful on its own. It also prevents the optional LLM path from becoming the source of truth about what the dataset contains.

## Human-authored context

Raw profile facts do not explain business meaning. Human-authored YAML context can mark important fields, known identifiers, fields to ignore, expected date fields, and field notes.

Context is optional, but it makes suggestions more meaningful. It also gives reviewers a place to state assumptions explicitly rather than relying on a model to infer them from column names alone.

## Safe summaries, not raw rows

The profile and evidence payload intentionally use aggregate summaries. They do not include raw rows, sampled records, source previews, top values, distinct value lists, raw failing rows, or raw failing values.

This boundary keeps review artifacts focused on evidence that is useful for candidate test suggestion without turning the tool into a raw-data sharing path.

## Active but bounded LLM candidate generation

The LLM path is optional, but it has a real job when enabled: propose structured candidate tests from the safe evidence payload.

The LLM is not decorative, and it is not authoritative. It receives safe evidence only, must return candidates in a narrow structure, and cannot approve tests, execute checks, bypass validation, create official coverage, or make legal, compliance, or privacy verdicts.

## Why not just ask an LLM?

A general LLM chat can invent columns, infer unsupported business rules, suggest tests that do not match the dataset, or return vague advice that cannot be validated. It can also encourage risky workflows, such as pasting raw rows into a prompt or accepting generated checks without review.

This project keeps responsibilities separate:

1. deterministic code profiles the dataset locally;
2. deterministic code builds a safe evidence payload;
3. optional LLM generation proposes structured candidates from that payload;
4. deterministic validation rejects unsupported, unsafe, or incompatible candidates;
5. optional execution runs only validated candidates with fixed local logic;
6. a human reviewer decides what to keep, rewrite, or discard.

## Deterministic validation after generation

Manual and LLM-generated candidates go through the same validator. Validation checks candidate shape, supported test type, severity, referenced columns, parameter shape, profile compatibility, context boundaries, and fields that look like executable code or row-level leakage.

Validation is a safety gate, not approval. A validated candidate can still be too strict, too weak, duplicated, or inappropriate for production use.

## Validated-only local execution

Execution is downstream of validation. The executor does not interpret candidate-provided code. It runs fixed local logic for supported test types and only for candidates that passed deterministic validation.

Rejected candidates are never executed. This keeps execution bounded, repeatable, and aggregate-only.

## Human reviewer authority

The report and JSON artifacts are review material. They do not approve candidates, certify that coverage is complete, or create an official production test suite.

A human reviewer decides whether a candidate becomes a dbt test, Great Expectations check, custom data quality rule, issue ticket, or nothing at all.

## Local-first execution

The core workflow runs locally and does not require an API key. OpenAI support is optional and installed only with the LLM extra. Deterministic profiling, context loading, manual candidate validation, optional local execution, and report generation work without calling an external model.

## Traceable artifacts

Each stage writes explicit artifacts when it runs. The trace records stage status and artifact paths. Profile, payload, validation, rejection, execution, and report artifacts are designed to make the workflow inspectable without storing raw dataset rows.

## Why `accepted_values` are not inferred from raw distinct values

Accepted-value tests can encode business rules, but raw distinct values are not automatically business rules. Inferring accepted values from current data can freeze historical mistakes, leak sensitive categories, or treat incomplete data as authoritative.

This project requires accepted-value candidates to come from a supplied candidate file or from bounded LLM generation that survives deterministic validation. A reviewer still decides whether the values reflect real expectations.

## Why rejected candidates can still be useful

Rejected candidates are written with reason codes instead of disappearing silently. Rejections can show that a candidate referenced an unknown column, used an unsupported test type, ignored context boundaries, supplied unsafe parameters, or tried to include row-level evidence or executable text.

That information can help reviewers improve context, rewrite manual candidates, or understand where generated suggestions exceeded the tool's boundaries.

## Why failed execution checks are review outcomes, not process failures

A failed executed check usually means the data did not satisfy the proposed rule. That is a review outcome about the dataset, not necessarily a process failure.

For example, a `not_null` candidate can execute successfully and report aggregate failures because nulls exist. The tool did its job: it ran a validated check locally and produced evidence for a human reviewer.
