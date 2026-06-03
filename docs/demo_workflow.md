# Demo workflow

This walkthrough shows the intended portfolio demo flow: install the project, run tests, run a deterministic end-to-end demo, inspect artifacts, optionally exercise LLM generation, read the report, and clean outputs.

## 1. Install

From the repository root, create and activate a virtual environment.

Bash:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

The base install includes deterministic local functionality and test dependencies. It does not install the optional OpenAI dependency.

## 2. Run tests

```bash
pytest
```

The expected CI shape is also simple:

```bash
pip install -e ".[dev]"
pytest
```

## 3. Run the deterministic demo

Use this command for the main demo because it does not require an API key and exercises profiling, context loading, manual candidate validation, deterministic execution, rejected candidate handling, and report generation.

```bash
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests_with_rejections.json \
  --execute-candidates \
  --write-report \
  --output-dir outputs
```

PowerShell can use the same command with backticks for line continuation:

```powershell
data-test-suggestion-agent `
  --input sample_data/customers/customers_for_test_suggestions.csv `
  --context config/examples/customer_dataset_context.yaml `
  --candidates config/examples/customer_candidate_tests_with_rejections.json `
  --execute-candidates `
  --write-report `
  --output-dir outputs
```

## 4. Inspect artifacts

List generated files:

```bash
find outputs -maxdepth 1 -type f | sort
```

PowerShell:

```powershell
Get-ChildItem outputs | Sort-Object Name
```

Expected files for the deterministic demo:

```text
outputs/data_test_trace.json
outputs/dataset_profile.json
outputs/rejected_test_suggestions.json
outputs/test_execution_results.json
outputs/test_suggestion_payload.json
outputs/test_suggestion_report.md
outputs/validated_test_suggestions.json
```

Suggested inspection order:

1. `outputs/test_suggestion_report.md` for the human-readable review summary.
2. `outputs/test_suggestion_payload.json` to see the safe aggregate evidence boundary.
3. `outputs/validated_test_suggestions.json` to see candidates that passed deterministic validation.
4. `outputs/rejected_test_suggestions.json` to see rejected candidates and reason codes.
5. `outputs/test_execution_results.json` to see aggregate pass/fail outcomes for validated checks.
6. `outputs/data_test_trace.json` to see run status and artifact paths.

## 5. Run the optional LLM demo

Only run this section if you want to exercise model-backed candidate generation. It requires the OpenAI extra, `OPENAI_API_KEY`, and either `DATA_TEST_AGENT_LLM_MODEL` or `--llm-model`.

Install the extra:

```bash
pip install -e ".[dev,llm]"
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
data-test-suggestion-agent \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --execute-candidates \
  --write-report \
  --output-dir outputs
```

The LLM path adds `outputs/llm_candidate_tests.json` when generation and parsing succeed. Those candidates still must pass deterministic validation and human review.

## 6. Read the report

Open the report in your editor:

```bash
sed -n '1,220p' outputs/test_suggestion_report.md
```

PowerShell:

```powershell
Get-Content outputs/test_suggestion_report.md -TotalCount 220
```

The report is deterministic human review material. It does not approve tests, certify coverage, make legal/compliance/privacy decisions, include raw rows, or include raw failing rows.

## 7. Clean outputs

Bash:

```bash
rm -rf outputs
```

PowerShell:

```powershell
Remove-Item -Recurse -Force outputs
```
