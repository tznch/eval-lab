#!/usr/bin/env python3
"""Convert samples.jsonl to promptfoo tests YAML."""

import argparse
import os
from pathlib import Path

import yaml

from shared.adapters.dataset_loader import load_samples
from shared.datasets.registry import get_dataset
from shared.eval.intent_matching import js_assert_intent, labels_for_prompt, write_intent_prompt

# Strip Gemma thinking blocks; score by keyword overlap with ground truth.
JS_ASSERT = r"""
function stripThinking(text) {
  const lines = String(text || '').split('\n');
  const kept = [];
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    if (!line) continue;
    if (/^thinking:/i.test(line)) continue;
    if (/^\*\s/.test(line)) continue;
    kept.unshift(line);
    if (kept.join(' ').length > 30) break;
  }
  return kept.join(' ').trim() || String(text || '').slice(-300);
}

const answer = stripThinking(output).toLowerCase();
const gt = String(context.vars.ground_truth || '').toLowerCase();
if (!answer || !gt) return false;
if (answer.includes(gt.slice(0, Math.min(40, gt.length)))) return true;

const keywords = [...new Set((gt.match(/\b[\w'-]{4,}\b/g) || []).filter(w => !/^(from|with|that|this|were|was|the|and|for)$/.test(w)))];
if (!keywords.length) return answer.includes(gt);
const hits = keywords.filter(k => answer.includes(k));
return hits.length >= Math.max(2, Math.ceil(keywords.length * 0.35));
""".strip()

PROMPTFOO_DIR = Path(__file__).resolve().parents[1] / "eval" / "promptfoo"
INTENT_PROMPT_RESOLVED = PROMPTFOO_DIR / "prompts" / "intent.resolved.txt"


def nunjucks_safe(text: str | None) -> str:
    """Prevent {{ }} in sample text from breaking Promptfoo/Nunjucks rendering."""
    if not text:
        return ""
    return text.replace("{{", "{ {").replace("}}", "} }")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=os.getenv("EVAL_DATASET", "feta"),
        help="Dataset config (feta|nq|sciq). Default: EVAL_DATASET or feta",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--output",
        default="eval/promptfoo/tests/generated.yaml",
    )
    args = parser.parse_args()

    samples = load_samples(args.config, args.limit)
    manifest = get_dataset(args.config)
    use_intent = (manifest and manifest.uses_intent_prompt) or (
        samples and samples[0].task_type == "intent"
    )

    if use_intent:
        labels = labels_for_prompt(manifest, samples)
        write_intent_prompt(labels, INTENT_PROMPT_RESOLVED)
        assert_js = js_assert_intent()
    else:
        assert_js = JS_ASSERT

    tests = []
    for s in samples:
        prompt_context = s.context or ("No context provided." if not use_intent else s.context)
        tests.append(
            {
                "description": s.id,
                "vars": {
                    "question": nunjucks_safe(s.question),
                    "context": nunjucks_safe(prompt_context),
                    "ground_truth": s.ground_truth,
                    "sample_id": s.id,
                },
                "metadata": {
                    "complexity": s.complexity,
                    "context_bucket": s.context_bucket,
                    "category": s.category,
                    "task_type": s.task_type,
                },
                "assert": [{"type": "javascript", "value": assert_js}],
            }
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        yaml.dump(tests, f, allow_unicode=True, default_flow_style=False)
    if use_intent:
        print(f"Wrote intent prompt ({len(labels)} labels) to {INTENT_PROMPT_RESOLVED}")
    print(f"Wrote {len(tests)} tests to {out}")


if __name__ == "__main__":
    main()
