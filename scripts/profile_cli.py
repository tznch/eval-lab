#!/usr/bin/env python3
"""Export/import secret-free run profiles."""

from __future__ import annotations

import argparse
from pathlib import Path

from shared.profiles.io import (
    export_profile_from_env,
    load_profile,
    save_profile,
    write_env_profile,
)


def cmd_export(args: argparse.Namespace) -> None:
    profile = export_profile_from_env(args.name)
    out = Path(args.out) if args.out else Path("profiles") / f"{args.name}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    save_profile(out, profile)
    print(f"Wrote {out}")


def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.profile)
    profile = load_profile(path)
    write_env_profile(profile)
    print(f"Loaded profile {profile.name!r} from {path}")
    print("Wrote .env.profile (gitignored). Non-secret overrides active for subsequent commands.")
    print("Download weights via Overview → Add from HuggingFace (or set {ID}_MODEL_PATH in .env).")
    for m in profile.models:
        hint = f" ({m.hf_repo})" if getattr(m, "hf_repo", None) else ""
        print(f"  model id: {m.id}{hint}")
    print(
        f"Example run: EVAL_DATASET={profile.dataset} TARGET_TEMPERATURE={profile.temperature} "
        f"PROMPTFOO_LIMIT={profile.limits.promptfoo} make lab MODEL={profile.models[0].id}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("export", help="Write YAML from current env/defaults")
    p_ex.add_argument("--name", required=True)
    p_ex.add_argument("--out", default=None)
    p_ex.set_defaults(func=cmd_export)

    p_im = sub.add_parser("import", help="Apply YAML to .env.profile")
    p_im.add_argument("--profile", required=True)
    p_im.set_defaults(func=cmd_import)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
