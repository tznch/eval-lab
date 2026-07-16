#!/usr/bin/env python3
"""List and prepare datasets from datasets/{id}/dataset.yaml."""

from __future__ import annotations

import argparse
import sys

from shared.datasets.prepare import prepare_dataset
from shared.datasets.registry import discover_datasets, get_dataset, list_dataset_ids


def cmd_list(_: argparse.Namespace) -> None:
    manifests = discover_datasets()
    if not manifests:
        print("No datasets found. Add datasets/{id}/dataset.yaml")
        return
    print(f"{'ID':<20} {'TYPE':<14} {'PORTFOLIO':<10} NAME")
    print("-" * 60)
    for m in manifests.values():
        pf = "yes" if m.eval.portfolio else ""
        print(f"{m.id:<20} {m.task_type:<14} {pf:<10} {m.name}")
    legacy = [i for i in list_dataset_ids() if i not in manifests]
    if legacy:
        print("\nLegacy (no dataset.yaml):", ", ".join(legacy))


def cmd_prepare(args: argparse.Namespace) -> None:
    path = prepare_dataset(args.dataset, args.limit)
    print(path)


def cmd_show(args: argparse.Namespace) -> None:
    m = get_dataset(args.dataset)
    if m is None:
        print(f"Unknown dataset: {args.dataset}", file=sys.stderr)
        sys.exit(1)
    print(f"id:          {m.id}")
    print(f"name:        {m.name}")
    print(f"task_type:   {m.task_type}")
    print(f"source:      {m.source.type} → {m.source.path}")
    print(f"eval.prompt: {m.eval.prompt}")
    print(f"portfolio:   {m.eval.portfolio}")
    print(f"samples:     {m.samples_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage datasets/ registry")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List registered datasets")
    p_list.set_defaults(func=cmd_list)

    p_prep = sub.add_parser("prepare", help="Prepare samples.jsonl from raw data")
    p_prep.add_argument("--dataset", "-d", required=True)
    p_prep.add_argument("--limit", "-n", type=int, default=None)
    p_prep.set_defaults(func=cmd_prepare)

    p_show = sub.add_parser("show", help="Show dataset manifest")
    p_show.add_argument("--dataset", "-d", required=True)
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
