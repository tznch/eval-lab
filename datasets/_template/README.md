# Dataset template

1. Copy this folder: `cp -r datasets/_template datasets/my_task`
2. Put CSV or JSONL files in `raw/`
3. Edit `dataset.yaml` — map your column names in `source.mapping`
4. Prepare: `make prepare-dataset DATASET=my_task`
5. Eval: `EVAL_DATASET=my_task make lab MODEL=<model_id>`

## Source types

| type | Use when |
|------|----------|
| `csv` | One or more CSV files in `raw/` |
| `jsonl` | JSONL with fields matching mapping |
| `samples` | Already-valid `EvalSample` JSONL (path in `source.path`) |
| `legacy` | Built-in HF preparer (`legacy: sciq`) — phase 2 migration |

## Task types

- `extractive_qa` — context + question → short answer
- `faq` — policy context + customer question
- `intent` — classify user message to intent label
