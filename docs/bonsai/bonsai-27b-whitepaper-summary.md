# Bonsai 27B — підсумок whitepaper (PrismML, липень 2026)

> Джерело: [bonsai-27b-whitepaper.pdf](./bonsai-27b-whitepaper.pdf)  
> Оригінал: [GitHub — PrismML-Eng/Bonsai-demo](https://github.com/PrismML-Eng/Bonsai-demo/raw/main/bonsai-27b-whitepaper.pdf)

## Архітектура, розмір і квантизація

| Параметр | Значення |
|----------|----------|
| **Базова модель** | [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B-FP8) — гібридна увага (~75% linear / ~25% full attention), SwiGLU MLP, RoPE, RMSNorm |
| **Параметри** | ~24.8B мовна частина (64 блоки) + 0.46B vision tower (27 блоків) + 2.5B embedding/LM head |
| **Контекст** | 262K токенів (завдяки переважно linear-attention backbone) |
| **Формати ваг** | **Ternary g128**: {−1, 0, +1} + FP16 group-wise scale на 128 ваг (~1.71 bpw) · **Binary g128**: {−1, +1} + FP16 scale (~1.125 bpw) |
| **End-to-end low-bit** | Embeddings, attention projections, MLP, LM head — усі у low-bit; vision tower окремо у 4-bit HQQ |
| **Розгортання** | ~5.9 GB (ternary, ідеал) / ~7.2 GB (ternary, packed) / ~3.9 GB (binary) |
| **KV-cache** | 4-bit за замовчуванням; Bonsai моделі толерантні до агресивнішої KV-компресії (на порядки менший forward-KL vs Qwen FP16/Q4) |
| **Прискорення** | Custom 1-bit/2-bit kernels для hybrid attention (MLX + CUDA); DSpark speculative decoding |
| **Ліцензія** | Apache 2.0 |

**Ключова ідея:** архітектура Qwen3.6-27B **не змінюється** — PrismML застосовує математично обґрунтовану **representation transformation** (IP Caltech) до вже натренованої моделі, на відміну від BitNet (pretrain from scratch у low-bit).

## Навчання та методологія

Whitepaper **не описує власний pretraining** Bonsai — модель успадковує знання та post-training Qwen3.6-27B. Власна методологія PrismML стосується:

1. **Квантизації ваг (Bonsai representation)** — перетворення pretrained FP16 мережі в binary/ternary з group-wise FP16 scaling (g128), без «escape hatch» high-precision тензорів, як у conventional GGUF.
2. **Попередні релізи** — Bonsai 1.7B–8B (binary + ternary) підтвердили підхід; 27B — перший масштаб із повною підтримкою thinking, CoT і tool use.
3. **DSpark drafter** — окремо натренований 6-шаровий drafter (hidden-state taps з 5 шарів target): diffusion-flavored block-denoising, distillation з вагою за ймовірністю виживання при verification; drafter також у 4-bit.
4. **KV calibration** — публічна методологія `kv-mean-center` ([PrismML-Eng/llama.cpp](https://github.com/PrismML-Eng/llama.cpp), `tools/kv-mean-center/make-calib-corpus.sh`).
5. **Оцінювання** — EvalScope + vLLM на H100; thinking mode; top-p 0.95, top-k 20; temp 0.7 (Bonsai) vs 1.0 (Qwen baseline).

## Бенчмарки vs інші моделі (особливо Qwen)

**15 бенчмарків** (thinking mode, unweighted mean): MMLU-Redux, MuSR, GSM8K, MATH-500, AIME25/26, HumanEval+, MBPP+, LiveCodeBench, IFEval, IFBench, BFCL v3, τ²-Bench, MMMU-Pro, OCR Bench v2.

### Середній бал (15 benchmarks)

| Варіант | True bpw | Розмір | Avg score | vs Qwen FP16 |
|---------|----------|--------|-----------|--------------|
| **Qwen3.6-27B FP16** | 16.0 | 54 GB | **85.07** | 100% |
| Qwen3.6-27B Q4_K_XL («4-bit») | 5.2 | 17.6 GB | 84.99 | 99.9% |
| Qwen3.6-27B IQ2_XXS («2-bit») | 2.8 | 9.4 GB | 72.73 | 85.5% |
| **Ternary Bonsai 27B** | 1.71 | 5.9 GB | **80.49** | 94.6% |
| **1-bit Bonsai 27B** | 1.125 | 3.9 GB | **76.11** | 89.5% |

Для контексту: Gemma-4-31B FP16 — 84.58; Gemma Q2_K_XL — 73.31 @ 11.8 GB.

### За категоріями (FP16 → Ternary → 1-bit)

| Категорія | FP16 | Ternary | 1-bit |
|-----------|------|---------|-------|
| Knowledge & reasoning | 83.15 | 76.96 | 73.39 |
| Math | 95.33 | 93.40 | 91.66 |
| Coding | 88.74 | 85.96 | 81.88 |
| Instruction following | 78.47 | 71.77 | 65.74 |
| Agentic / tool calling | 80.00 | 74.01 | 66.03 |
| Vision | 72.61 | 65.19 | 59.57 |

### Де conventional low-bit «ламається», а Bonsai тримається

| Benchmark | Qwen IQ2_XXS | Ternary Bonsai | 1-bit Bonsai | Qwen FP16 |
|-----------|--------------|----------------|--------------|-----------|
| AIME26 | 57.5 | 87.5 | 87.1 | 93.3 |
| AIME25 | 66.7 | 90.8 | 88.8 | 93.3 |
| LiveCodeBench | 56.4 | 82.8 | 76.4 | 87.8 |
| MMLU-Redux | 88.9 | 88.1 | 82.8 | 93.4 |
| IFEval | 84.0 | 85.0 | 79.1 | 88.9 |
| τ²-Bench | 74.6 | 73.6 | 61.3 | 82.9 |

**Висновок whitepaper:** aggregate score IQ2_XXS оманливий — короткі MCQ-бенчмарки маскують колапс на довгих ланцюгах міркувань, coding і agentic tasks. Bonsai зберігає ці «важкі» категорії набагато краще при меншому footprint.

### Intelligence density (інтелект / GB)

1-bit Bonsai: **0.530** · Ternary: **0.400** · Qwen IQ2_XXS: 0.199 · Qwen FP16: 0.051.

### Throughput (edge, tg128 tok/s)

| Платформа | Binary (~3.9 GB) | Ternary (~7.2 GB) |
|-----------|------------------|-------------------|
| Laptop M5 Pro | 44.2 | 26.2 |
| Laptop M5 Max | 66.4 | 44.0 |
| iPhone 17 Pro Max | 11.0 | — (не вміщується) |
| H100 CUDA | 104.8 | 98.0 |

## Рекомендовані кути оцінювання для llmtesting lab

Наш lab ([README](../../README.md)) уже запускає Bonsai-27B-Q1 через `llama-server` на CPU (:8081) з Promptfoo, DeepEval і RAGAS. Whitepaper підказує, **де саме** варто фокусувати eval, щоб не повторити помилку «casual testing»:

### 1. Довгі ланцюги міркувань (пріоритет №1)

- **AIME-style / multi-step math** — whitepaper показує найбільший розрив між IQ2 і Bonsai.
- Розширити SciQ на складніші science reasoning tasks або додати math track (GSM8K subset).
- Увімкнути **thinking mode** там, де підтримується; порівнювати з Gemma-4 baseline.

### 2. Agentic / tool calling

- **BFCL v3, τ²-Bench** — найбільший drop у 1-bit (66.03 vs 80.00 FP16).
- Додати Promptfoo tests з structured tool calls (JSON schema, multi-turn).
- Перевірити retail intent dataset (`bitext_retail`) на multi-turn agent loops.

### 3. Instruction following

- **IFEval mini-track** вже є (`make eval-promptfoo-ifeval`) — розширити до IFBench-style loose constraints.
- 1-bit Bonsai: 65.74 category avg — очікувати слабші результати vs ternary; документувати trade-off.

### 4. Coding (наступний реліз PrismML)

- Whitepaper roadmap: **agentic coding variant** «next».
- Поки що: HumanEval+/LiveCodeBench-style prompts у Promptfoo; порівняння Bonsai vs Gemma на coding subset.

### 5. Long-context + KV tolerance

- Bonsai толерантний до 4-bit KV — протестувати **довгі контексти** (UDA-QA, full-repo prompts) на CPU з обмеженою RAM.
- Виміряти degradation при 32K/64K/100K context vs короткі промпти.

### 6. RAG quality (наш core stack)

- RAGAS на UDA-QA (`feta`, `nq`) — перевірити, чи low-bit не «ламить» retrieval-grounded відповіді.
- DeepEval faithfulness/relevancy на довгих evidence chains.

### 7. Latency / throughput на minipc

- Whitepaper: bandwidth-bound decode; наш Ryzen AI 9 HX 470 + 59 GB RAM — виміряти **tok/s** і p95 latency для Bonsai Q1 vs Gemma Q4.
- Документувати CPU-only vs їхні Apple/CUDA цифри.

### 8. Що НЕ перевіряти як sole metric

- Короткі MCQ (MMLU-style) — маскують collapse conventional quant; не використовувати лише SciQ pass-rate як єдиний показник якості.

## Обмеження та roadmap (з whitepaper)

- Ternary/binary = 94.6% / 89.5% від FP16 avg; найбільший gap у agentic, IF та vision.
- Agentic coding variant — у roadmap.
- Native ternary kernels (зараз 2-bit slots) — майбутнє зменшення footprint.
- Sub-2-bit KV — early results позитивні.
- DSpark на Apple Silicon batch-1 ще не дає net-positive speedup.

## Посилання

| Ресурс | URL |
|--------|-----|
| **Локальний PDF** | [docs/bonsai/bonsai-27b-whitepaper.pdf](./bonsai-27b-whitepaper.pdf) |
| **GitHub (оригінал PDF)** | https://github.com/PrismML-Eng/Bonsai-demo/raw/main/bonsai-27b-whitepaper.pdf |
| **1-bit GGUF (HuggingFace)** | https://huggingface.co/prism-ml/Bonsai-27B-gguf |
| **Ternary GGUF** | https://huggingface.co/prism-ml/Ternary-Bonsai-27B-gguf |
| **Qwen3.6-27B base** | https://huggingface.co/Qwen/Qwen3.6-27B-FP8 |
| **Qwen3 tech report** | arXiv:2505.09388 |
| **PrismML llama.cpp fork** | https://github.com/PrismML-Eng/llama.cpp |
| **1-bit Bonsai 8B report** | PrismML, March 2026 |
| **Ternary Bonsai 8B report** | PrismML, April 2026 |
