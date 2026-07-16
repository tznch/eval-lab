"""Intent label normalization and synonym matching for Promptfoo asserts."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from shared.datasets.manifest import DatasetManifest
from shared.datasets.registry import resolve_source_files
from shared.schemas.eval_sample import EvalSample

# Canonical ground-truth label -> accepted model output variants (snake_case).
INTENT_SYNONYMS: dict[str, frozenset[str]] = {
    "add_product": frozenset(
        {
            "add_product",
            "add_to_cart",
            "add_item",
            "add_item_to_cart",
            "add_items_to_basket",
            "add_items_to_cart",
            "add_to_basket",
            "add_items",
            "add_product_to_cart",
        }
    ),
    "remove_product": frozenset(
        {
            "remove_product",
            "remove_from_cart",
            "remove_item",
            "delete_product",
            "remove_items",
        }
    ),
    "track_order": frozenset({"track_order", "order_tracking", "order_status", "check_order"}),
    "track_delivery": frozenset(
        {
            "track_delivery",
            "delivery_tracking",
            "track_shipment",
            "shipping_status",
            "delivery_time",
            "delivery_date",
        }
    ),
    "delivery_time": frozenset(
        {
            "delivery_time",
            "track_delivery",
            "delivery_date",
            "estimated_delivery",
            "delivery_tracking",
        }
    ),
    "cancel_order": frozenset({"cancel_order", "order_cancellation", "cancel_purchase"}),
    "change_order": frozenset({"change_order", "modify_order", "edit_order"}),
    "return_product": frozenset(
        {
            "return_product",
            "return_item",
            "product_return",
            "return_product_online",
            "return_product_in_store",
        }
    ),
    "exchange_product": frozenset(
        {
            "exchange_product",
            "exchange_item",
            "product_exchange",
            "exchange_product_in_store",
        }
    ),
    "recover_password": frozenset(
        {"recover_password", "reset_password", "password_recovery", "forgot_password"}
    ),
    "open_account": frozenset({"open_account", "create_account", "register_account", "sign_up"}),
    "close_account": frozenset({"close_account", "delete_account", "deactivate_account"}),
}


def normalize_intent_label(text: str | None) -> str:
    """Lowercase snake_case label from model output or CSV ground truth."""
    if not text:
        return ""
    line = str(text).strip().split("\n")[-1].strip()
    line = re.sub(r"[^a-zA-Z0-9_ ]+", " ", line.lower())
    return "_".join(line.split())


def intent_labels_match(predicted: str | None, expected: str | None) -> bool:
    """Return True if predicted intent matches expected (exact or synonym)."""
    answer = normalize_intent_label(predicted)
    target = normalize_intent_label(expected)
    if not answer or not target:
        return False
    if answer == target:
        return True
    if answer in target or target in answer:
        return True

    aliases = INTENT_SYNONYMS.get(target, frozenset({target}))
    if answer in aliases:
        return True

    for alias in aliases:
        norm = normalize_intent_label(alias)
        if answer == norm or answer in norm or norm in answer:
            return True
        parts = [p for p in norm.split("_") if len(p) > 2]
        if len(parts) >= 2 and all(p in answer for p in parts):
            return True

    parts = [p for p in target.split("_") if len(p) > 2]
    if parts and all(p in answer for p in parts):
        return True
    return False


def synonyms_for_js() -> dict[str, list[str]]:
    return {k: sorted(v) for k, v in INTENT_SYNONYMS.items()}


def js_assert_intent() -> str:
    """Promptfoo JavaScript assert with embedded synonym map."""
    syn_json = json.dumps(synonyms_for_js())
    return f"""
function stripThinking(text) {{
  return String(text || '').trim().split('\\n').pop().trim();
}}
function normalizeIntent(text) {{
  return stripThinking(text).toLowerCase().replace(/[^a-z0-9_ ]/g, ' ').trim().replace(/\\s+/g, '_');
}}
const SYNONYMS = {syn_json};
function matchesIntent(output, groundTruth) {{
  const answer = normalizeIntent(output);
  const expected = normalizeIntent(groundTruth);
  if (!answer || !expected) return false;
  if (answer === expected || answer.includes(expected) || expected.includes(answer)) return true;
  const aliases = SYNONYMS[expected] || [expected];
  for (const alias of aliases) {{
    const norm = normalizeIntent(alias);
    if (answer === norm || answer.includes(norm) || norm.includes(answer)) return true;
    const parts = norm.split('_').filter(p => p.length > 2);
    if (parts.length >= 2 && parts.every(p => answer.includes(p))) return true;
  }}
  const expParts = expected.split('_').filter(p => p.length > 2);
  if (expParts.length && expParts.every(p => answer.includes(p))) return true;
  return false;
}}
return matchesIntent(output, context.vars.ground_truth);
""".strip()


def _unique_labels_from_csv(path: Path, column: str) -> list[str]:
    labels: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            val = str(row.get(column) or "").strip()
            if val:
                labels.add(val)
    return sorted(labels)


def vocabulary_for_manifest(manifest: DatasetManifest | None) -> list[str]:
    """All intent labels from dataset source (e.g. retail CSV)."""
    if manifest is None or manifest.source.type not in ("csv", "jsonl"):
        return []
    gt_col = manifest.source.mapping.get("ground_truth", "ground_truth")
    labels: set[str] = set()
    for fp in resolve_source_files(manifest):
        if fp.suffix.lower() == ".csv":
            labels.update(_unique_labels_from_csv(fp, gt_col))
    return sorted(labels)


def labels_for_prompt(manifest: DatasetManifest | None, samples: list[EvalSample]) -> list[str]:
    """Label list for resolved intent prompt: full vocabulary + sample labels."""
    vocab = set(vocabulary_for_manifest(manifest))
    vocab.update(s.ground_truth for s in samples if s.ground_truth)
    return sorted(vocab)


def write_intent_prompt(labels: list[str], out_path: Path) -> None:
    """Write dataset-specific intent prompt with exact snake_case label list."""
    if labels:
        label_block = ", ".join(labels)
        examples = ", ".join(labels[:4])
        label_section = f"""Valid labels (snake_case — reply with exactly one):
{label_block}"""
    else:
        examples = "cancel_order, add_product, track_order"
        label_section = f"""Use snake_case intent labels (e.g. {examples})."""

    out_path.write_text(
        f"""Classify the user message into exactly one support intent label.

{label_section}

User message:
{{{{question}}}}

Reply with only the intent label from the list above. No explanation.""",
        encoding="utf-8",
    )
