#!/usr/bin/env python3
"""Download google/IFEval and emit Promptfoo tests with rule-based asserts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from datasets import load_dataset

from shared.hf_auth import get_hf_token

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "ifeval"
OUT_TESTS = ROOT / "eval" / "promptfoo" / "tests" / "ifeval.yaml"
REPO = "google/IFEval"

# Lightweight checkers for a useful IFEval subset (no full IFEval package).
JS_ASSERT = r"""
function wordCount(text) {
  return String(text || '').trim().split(/\s+/).filter(Boolean).length;
}

const output = String(output || '');
const ids = JSON.parse(context.vars.instruction_ids || '[]');
const kwargs = JSON.parse(context.vars.instruction_kwargs || '[]');

for (let i = 0; i < ids.length; i++) {
  const id = ids[i];
  const kw = kwargs[i] || {};

  if (id === 'punctuation:no_comma') {
    if (output.includes(',')) return false;
  }
  if (id === 'length_constraints:number_words') {
    const n = wordCount(output);
    const rel = kw.relation || 'at least';
    const need = Number(kw.num_words || 0);
    if (rel === 'at least' && n < need) return false;
    if (rel === 'at most' && n > need) return false;
  }
  if (id === 'length_constraints:number_sentences') {
    const n = (output.match(/[.!?]+/g) || []).length;
    const rel = kw.relation || 'at least';
    const need = Number(kw.num_sentences || 0);
    if (rel === 'at least' && n < need) return false;
    if (rel === 'at most' && n > need) return false;
  }
  if (id === 'detectable_format:number_highlighted_sections') {
    // Count *section* or **section** style highlights
    const n = (output.match(/\*[^*\n]+\*/g) || []).length;
    const need = Number(kw.num_highlights || 0);
    if (n < need) return false;
  }
  if (id === 'detectable_format:number_bullet_lists') {
    const n = (output.match(/^\s*[-*•]\s+/gm) || []).length;
    const need = Number(kw.num_bullets || kw.num_highlights || 1);
    if (n < need) return false;
  }
  if (id === 'startend:end_checker') {
    const ender = String(kw.end_phrase || '').trim();
    if (ender && !output.trim().endsWith(ender)) return false;
  }
  if (id === 'startend:quotation') {
    const t = output.trim();
    if (!(t.startsWith('"') && t.endsWith('"'))) return false;
  }
}
return true;
""".strip()

SUPPORTED = {
    "punctuation:no_comma",
    "length_constraints:number_words",
    "length_constraints:number_sentences",
    "detectable_format:number_highlighted_sections",
    "detectable_format:number_bullet_lists",
    "startend:end_checker",
    "startend:quotation",
}


def _supported(row: dict) -> bool:
    ids = row.get("instruction_id_list") or []
    return bool(ids) and all(i in SUPPORTED for i in ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare IFEval Promptfoo tests")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    token = get_hf_token()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Loading {REPO} ...")
    ds = load_dataset(REPO, split="train", token=token)

    selected = []
    for row in ds:
        if not _supported(dict(row)):
            continue
        selected.append(dict(row))
        if len(selected) >= args.limit:
            break

    raw_out = RAW_DIR / "selected.jsonl"
    with raw_out.open("w", encoding="utf-8") as f:
        for row in selected:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    tests = []
    for row in selected:
        key = row.get("key", len(tests))
        ids = list(row.get("instruction_id_list") or [])
        kwargs = list(row.get("kwargs") or [])
        # Normalize kwargs for JSON (datasets may use None)
        kwargs = [k if isinstance(k, dict) else {} for k in kwargs]
        tests.append(
            {
                "description": f"ifeval_{key}",
                "vars": {
                    "prompt": row["prompt"],
                    "instruction_ids": json.dumps(ids),
                    "instruction_kwargs": json.dumps(kwargs),
                },
                "assert": [{"type": "javascript", "value": JS_ASSERT}],
            }
        )

    OUT_TESTS.parent.mkdir(parents=True, exist_ok=True)
    OUT_TESTS.write_text(
        yaml.dump(tests, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(tests)} IFEval tests → {OUT_TESTS}")
    print(f"Raw selection → {raw_out}")


if __name__ == "__main__":
    main()
