"""Dataset registry and generic prepare from datasets/{id}/dataset.yaml."""

from shared.datasets.manifest import DatasetManifest
from shared.datasets.registry import (
    datasets_root,
    discover_datasets,
    get_dataset,
    list_dataset_ids,
    portfolio_dataset_ids,
    samples_path,
)
from shared.datasets.prepare import prepare_dataset

__all__ = [
    "DatasetManifest",
    "datasets_root",
    "discover_datasets",
    "get_dataset",
    "list_dataset_ids",
    "portfolio_dataset_ids",
    "prepare_dataset",
    "samples_path",
]
