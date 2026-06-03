# Demo workflow

This walkthrough shows a local end-to-end workflow: install the project, run tests, run the recommended deterministic demo, inspect artifacts, optionally exercise LLM generation, read the report, and clean outputs.

All commands assume you are running from the repository root.

## 1. Install

Create and activate a virtual environment if you want an isolated local setup.

Bash:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The base install includes deterministic local functionality and test dependencies. It does not install the optional OpenAI dependency.

## 2. Run tests

```bash
python -m pytest -q
```

The CI-style command sequence is intentionally simple:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## 3. Run the recommended deterministic demo

Use this command for the main local demo. It does not require an API key, and it exercises profiling, context loading, manual candidate validation, deterministic execution, rejected candidate handling, and report generation.

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests_with_rejections.json \
  --execute-candidates \
  --write-report \
  --output-dir outputs/customer_test_review
```

PowerShell can use backticks for line continuation:

```powershell
python -m data_test_suggestion_agent.cli `
  --input sample_data/customers/customers_for_test_suggestions.csv `
  --context config/examples/customer_dataset_context.yaml `
  --candidates config/examples/customer_candidate_tests_with_rejections.json `
  --execute-candidates `
  --write-report `
  --output-dir outputs/customer_test_review
```

## 4. Inspect artifacts

List generated files:

```bash
find outputs/customer_test_review -maxdepth 1 -type f | sort
```

PowerShell:

```powershell
Get-ChildItem outputs/customer_test_review | Sort-Object Name
```

Expected files for the deterministic demo:

```text
outputs/customer_test_review/data_test_trace.json
outputs/customer_test_review/dataset_profile.json
outputs/customer_test_review/rejected_test_suggestions.json
outputs/customer_test_review/test_execution_results.json
outputs/customer_test_review/test_suggestion_payload.json
outputs/customer_test_review/test_suggestion_report.md
outputs/customer_test_review/validated_test_suggestions.json
```

Suggested inspection order:

1. `outputs/customer_test_review/test_suggestion_report.md` for the human-readable review summary.
2. `outputs/customer_test_review/test_suggestion_payload.json` to see the safe aggregate evidence boundary.
3. `outputs/customer_test_review/validated_test_suggestions.json` to see candidates that passed deterministic validation.
4. `outputs/customer_test_review/rejected_test_suggestions.json` to see rejected candidates and reason codes.
5. `outputs/customer_test_review/test_execution_results.json` to see aggregate pass/fail outcomes for validated checks.
6. `outputs/customer_test_review/data_test_trace.json` to see run status and artifact paths.

## 5. Run the optional LLM demo

Only run this section if you want to exercise model-backed candidate generation. It requires the OpenAI extra, `OPENAI_API_KEY`, and either `DATA_TEST_AGENT_LLM_MODEL` or `--llm-model`.

Install the extra:

```bash
python -m pip install -e ".[dev,llm]"
```

Set environment variables in Bash:

```bash
export OPENAI_API_KEY="..."
export DATA_TEST_AGENT_LLM_MODEL="your-model-name"
```

Or in PowerShell:

```powershell
$env:OPENAI_API_KEY = "..."
$env:DATA_TEST_AGENT_LLM_MODEL = "your-model-name"
```

Run generation, validation, execution, and reporting:

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

The LLM path adds `outputs/customer_test_review_llm/llm_candidate_tests.json` when generation and parsing succeed. Those candidates still must pass deterministic validation and human review.

## 6. Read the report

Open the deterministic demo report in your editor, or preview it from the terminal:

```bash
sed -n '1,220p' outputs/customer_test_review/test_suggestion_report.md
```

PowerShell:

```powershell
Get-Content outputs/customer_test_review/test_suggestion_report.md -TotalCount 220
```

The report is deterministic human review material. It does not approve tests, certify coverage, make legal/compliance/privacy decisions, include raw rows, or include raw failing rows.

## 7. Clean outputs

Bash:

```bash
rm -rf outputs/customer_test_review outputs/customer_test_review_llm
```

PowerShell:

```powershell
Remove-Item -Recurse -Force outputs/customer_test_review, outputs/customer_test_review_llm
```
