import json
from pathlib import Path

from shared.schemas.eval_sample import EvalSample

PROCESSED_ROOT = Path("data/processed")


def samples_dir(config: str) -> Path:
    from shared.datasets.registry import get_dataset, samples_path

    path = samples_path(config)
    if path.exists() or get_dataset(config) is not None:
        return path.parent
    return PROCESSED_ROOT / "uda-qa" / config


def samples_path_for(config: str) -> Path:
    from shared.datasets.registry import samples_path

    return samples_path(config)


def save_samples(samples: list[EvalSample], config: str) -> Path:
    path = samples_path_for(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for sample in samples:
            f.write(sample.model_dump_json() + "\n")
    return path


def load_samples(config: str, limit: int | None = None) -> list[EvalSample]:
    path = samples_path_for(config)
    if not path.exists():
        hint = f"python scripts/dataset_cli.py prepare --dataset {config}"
        if config == "sciq":
            hint = (
                "python scripts/download_sciq.py && "
                "python scripts/dataset_cli.py prepare --dataset sciq"
            )
        raise FileNotFoundError(f"No samples at {path}. Run: {hint}")
    samples: list[EvalSample] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(EvalSample.model_validate_json(line))
            if limit is not None and len(samples) >= limit:
                break
    return samples


def load_samples_from_jsonl(path: Path, limit: int | None = None) -> list[EvalSample]:
    samples: list[EvalSample] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(EvalSample.model_validate_json(line))
            if limit is not None and len(samples) >= limit:
                break
    return samples


def samples_to_json(samples: list[EvalSample]) -> list[dict]:
    return [json.loads(s.model_dump_json()) for s in samples]
