# Comparable baselines: Bonsai vs Qwen3.6-27B

## What the whitepaper compares

Bonsai 27B is a **representation transform** of [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B-FP8), not a new pretrain. PrismML benchmarks against:

| Variant | Quant | Size | 15-benchmark avg | Role |
|---------|-------|------|------------------|------|
| Qwen3.6-27B FP16 | 16 bpw | 54 GB | 85.07 | Upper bound (reference) |
| **Qwen3.6-27B Q4_K_XL** | ~5.2 bpw | 17.6 GB | 84.99 | Strong conventional quant |
| **Qwen3.6-27B IQ2_XXS** | ~2.8 bpw | 9.4 GB | 72.73 | Conventional ultra-low-bit |
| Bonsai ternary | 1.71 bpw | 5.9 GB | 80.49 | PrismML transform |
| **Bonsai 1-bit (Q1)** | 1.125 bpw | ~3.9 GB | 76.11 | Our local GGUF (~3.6 GB) |

Also mentioned: Gemma-4-31B FP16 (84.58), Gemma Q2_K_XL (73.31 @ 11.8 GB).

Full summary: [docs/bonsai/bonsai-27b-whitepaper-summary.md](../bonsai/bonsai-27b-whitepaper-summary.md)

## Our local lab mapping

| Lab model ID | GGUF | Port | Whitepaper analogue |
|--------------|------|------|---------------------|
| `bonsai` | `prism-ml/Bonsai-27B-gguf` Q1_0 | 8081 | Bonsai 1-bit |
| **`qwen27`** | `unsloth/Qwen3.6-27B-GGUF` **UD-IQ2_XXS** | 8082 | **Qwen IQ2_XXS** |

**Same eval stack for both:** identical `samples.jsonl`, HY3 judge, Promptfoo + DeepEval + RAGAS, portfolio datasets.

**Sequential only:** stop Bonsai before starting Qwen (`make stop-servers`). Two 27B models must not load at once on CPU.

## Commands

```bash
# Bonsai portfolio (already run)
TARGET_TEMPERATURE=0.2 make portfolio MODEL=bonsai

# Qwen comparable — same datasets, stops other servers first
TARGET_TEMPERATURE=0.2 make portfolio-qwen27

# Or step-by-step
make download-qwen27
make stop-servers
make portfolio-qwen27 PORTFOLIO_LIMIT=25
```

## How to read results

- **Dashboard → Report:** side-by-side bars for `bonsai` and `qwen27`
- **Failures:** stratified pass rate by complexity / context length
- **Whitepaper numbers:** external reference only (different harness: EvalScope + vLLM + thinking mode)
- **Our numbers:** product-like RAG/FAQ/intent tracks — the apples-to-apples comparison is **bonsai vs qwen27 on the same portfolio**

## Temperature note

Whitepaper uses temp **0.7** (Bonsai) vs **1.0** (Qwen). For local portfolio parity, use the same `TARGET_TEMPERATURE` for both runs (default **0.2** in comparable script).
