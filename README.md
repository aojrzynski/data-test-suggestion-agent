# Data Test Suggestion Agent

Data Test Suggestion Agent is a local-first Python CLI project that will eventually help answer:

> What data tests should we add for this dataset?

The intended direction is to combine deterministic evidence collection with reviewable candidate test suggestions. If LLM-assisted candidate generation is added later, it will be bounded and optional. The agent will eventually produce reviewable candidate data tests, not automatically approved test coverage. Human reviewers decide what becomes official.

## Current status

This repository is scaffold only. It does not analyze datasets or suggest tests yet.

This first PR adds:

- a Python package named `data_test_suggestion_agent`
- a CLI command named `data-test-suggestion-agent`
- a deterministic scaffold trace written as JSON
- pytest coverage for the scaffold CLI
- a GitHub Actions workflow that runs the tests

## What is intentionally not implemented yet

This scaffold does not include:

- dataset loading
- CSV, XLSX, or XLSM support
- worksheet selection
- profiling
- YAML context files
- evidence payload construction
- LLM calls
- candidate test models
- test validation
- test execution
- markdown reports

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
data-test-suggestion-agent --output-dir outputs
```

## Expected output artifact

A normal scaffold run creates the output directory if needed and writes:

```text
outputs/data_test_trace.json
```

The trace records that the scaffold completed and that future stages are `not_implemented`.

## Authority boundary

This project is designed around human review. Future versions may generate candidate tests, but those candidates should be treated as suggestions for review. The tool should not claim that suggested tests are complete, correct, or approved without human decision-making.

The scaffold does not send raw rows to any model, does not call an LLM, and does not make legal, privacy, or compliance verdicts.
