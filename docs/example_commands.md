# Example commands

These commands are meant to be copy-paste friendly from the repository root. They use `python -m data_test_suggestion_agent.cli` so they work even before console scripts are installed.

## Profile only

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --output-dir outputs/profile_only
```

Writes the trace, dataset profile, and safe evidence payload.

## Profile with context

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --output-dir outputs/profile_with_context
```

Adds human-authored dataset context to the safe evidence payload.

## Manual candidates, validation only

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests_with_rejections.json \
  --output-dir outputs/manual_validation
```

Validates manual candidates and writes accepted-for-review and rejected candidate artifacts. Accepted-for-review candidates are still not approved tests.

## Manual candidates with execution and report

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --candidates config/examples/customer_candidate_tests_with_rejections.json \
  --execute-candidates \
  --write-report \
  --output-dir outputs/manual_execution_report
```

Runs only validated candidates with fixed local logic and writes a deterministic Markdown report.

## Optional LLM generation

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --output-dir outputs/llm_generation
```

Requires `python -m pip install -e ".[dev,llm]"`, `OPENAI_API_KEY`, and either `DATA_TEST_AGENT_LLM_MODEL` or `--llm-model`.

## Optional LLM generation with execution and report

```bash
python -m data_test_suggestion_agent.cli \
  --input sample_data/customers/customers_for_test_suggestions.csv \
  --context config/examples/customer_dataset_context.yaml \
  --generate-candidates \
  --max-candidates 8 \
  --execute-candidates \
  --write-report \
  --output-dir outputs/llm_execution_report
```

The LLM proposes candidates from safe evidence. Deterministic validation still decides which candidates are eligible for local execution.

## Excel sheet command

```bash
python -m data_test_suggestion_agent.cli \
  --input path/to/workbook.xlsx \
  --sheet Sheet1 \
  --context config/examples/customer_dataset_context.yaml \
  --output-dir outputs/excel_profile
```

This command assumes the workbook exists locally and that `Sheet1` is the intended sheet name.
