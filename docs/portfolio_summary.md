# Portfolio summary

## What does this agent do?

Data Test Suggestion Agent is a local-first Python CLI that helps a reviewer decide what data tests might be useful for a dataset. It loads a local CSV or Excel file, profiles it into safe aggregate evidence, optionally combines that evidence with human-authored YAML context, optionally asks an LLM for structured candidate tests, validates candidates deterministically, optionally executes validated checks locally, and writes a Markdown report for human review.

The project is built around a practical question: what data tests should we add for this dataset?

## Why is it useful?

Data quality work often starts with ambiguity. A team may know that a dataset should have tests, but not know whether to start with uniqueness checks, null checks, date checks, accepted values, numeric ranges, or regex patterns.

This agent creates a reviewable starting point. It turns a local dataset into safe evidence, combines that evidence with human context when available, and produces candidate checks that a reviewer can accept, rewrite, or reject outside the tool.

## Why is the design safer than “just ask an LLM”?

The LLM is not the authority. It is an optional brainstorming step behind a narrow boundary.

The safer pattern is:

1. Build aggregate evidence locally without raw rows.
2. Send only the safe evidence payload to the LLM when generation is requested.
3. Require structured candidate output.
4. Run deterministic validation after generation.
5. Execute only validated candidates with fixed local logic.
6. Produce a deterministic report that clearly says candidates are not approved tests.
7. Leave the final decision to a human reviewer.

This design avoids raw row sharing with the model, avoids arbitrary generated code execution, avoids automatic approval, and avoids claims that test coverage is complete.

## What technical skills does it demonstrate?

The project demonstrates:

- Python package and CLI design.
- Typed dataclasses and explicit data contracts.
- pandas-based CSV and Excel intake.
- Safe aggregate profiling.
- YAML context loading and validation.
- Deterministic JSON artifact generation.
- Optional OpenAI integration behind an extra dependency.
- Structured LLM output handling.
- Deterministic validation of model or human-supplied candidates.
- Bounded local execution of supported checks.
- Markdown report generation.
- pytest-based testing and CI-friendly commands.
- Product judgment around human-in-the-loop AI systems.

## How would I talk about it in an interview?

A concise interview explanation:

> I built a local-first CLI agent for data test suggestion. It profiles a dataset into aggregate-only evidence, optionally adds human-authored context, and can use an LLM to propose structured candidate tests. The key design choice is that the LLM only proposes. Deterministic Python code validates candidates, optional local execution only runs validated checks, and the final Markdown report is for human review only. The project demonstrates agentic workflow design without giving the model authority over data quality decisions.

If asked about tradeoffs, emphasize that the tool is intentionally conservative. It does not export row-level failures, execute generated code, infer final accepted values from raw distinct values, or generate an approved production test suite. Those boundaries make the project smaller, but they also make the workflow easier to reason about and safer to review.
