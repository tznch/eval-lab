MODEL_REGISTRY: dict[str, dict[str, str]] = {
    "bonsai": {
        "hf_repo": "prism-ml/Bonsai-27B-gguf",
        "quant": "Q1_0",
        "gguf_hint": "data/models/bonsai-27b-q1/",
        "filename": "Bonsai-27B-Q1_0.gguf",
    },
    "qwen27": {
        "hf_repo": "unsloth/Qwen3.6-27B-GGUF",
        "quant": "UD-IQ2_XXS",
        "gguf_hint": "data/models/qwen3.6-27b-iq2/",
        "filename": "Qwen3.6-27B-UD-IQ2_XXS.gguf",
    },
}
