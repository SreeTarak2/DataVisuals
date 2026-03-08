# Chatbot Prompt Evaluation Guide

Use this after frontend/chat fixes to evaluate response quality and drive prompt updates.

## 1) Start backend in your own terminal

Run your normal backend startup command first.

## 2) Run evaluation script

From `version2/backend`:

```bash
source .venv/bin/activate
python scripts/chatbot_eval_runner.py \
  --base-url http://localhost:8000 \
  --email "<your-email>" \
  --password "<your-password>" \
  --dataset-id "<dataset-id>" \
  --modes deep learning quick \
  --queries-file scripts/chatbot_eval_queries.json
```

If `--dataset-id` is omitted, the first dataset for the user is used.

## 3) Review generated outputs

Each run writes to `evals/<timestamp>/`:

- `results.jsonl`: Full raw run logs (best for automation)
- `results.csv`: Flat table for quick scan
- `scoring_template.csv`: Fill this manually for prompt tuning
- `summary.md`: Basic run statistics

## 4) Score each response (1-5)

Fill these columns in `scoring_template.csv`:

- `faithfulness_1_5`: grounded in data context, no invention
- `analytical_depth_1_5`: goes beyond surface-level commentary
- `specificity_1_5`: concrete numbers/segments/caveats
- `actionability_1_5`: clear next decisions or actions
- `format_quality_1_5`: readable, structured, follows markdown rules
- `prompt_fix_notes`: exact prompt issue and suggested fix

## 5) Convert notes into prompt changes

For each recurring failure pattern, update prompts in:

- `core/prompt_templates.py`
- `services/llm_router.py` (`_build_system_prompt`, complexity hints)
- `core/prompts.py` (prompt assembly and context construction)

Use this pattern for prompt edits:

1. Failure pattern (example bad response behavior)
2. Prompt rule to add/change
3. Expected output behavior
4. Re-run eval to confirm fix

## Suggested regression gate

Treat prompt update as acceptable only if:

- No increase in error rate
- Average `faithfulness_1_5` and `analytical_depth_1_5` both improve
- Multi-turn memory chain responses remain coherent
