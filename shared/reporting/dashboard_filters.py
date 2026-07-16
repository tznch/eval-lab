"""Server-side filter parsing and application for dashboard partials."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FilterState:
    models: list[str] = field(default_factory=list)
    temps: list[str] = field(default_factory=list)
    dataset: str = "all"
    frameworks: list[str] = field(default_factory=list)

    def matches_run(self, model: str, temp_tag: str) -> bool:
        if self.models and model not in self.models:
            return False
        if self.temps and temp_tag not in self.temps:
            return False
        return True

    def matches_dataset(self, dataset: str) -> bool:
        return self.dataset == "all" or self.dataset == dataset

    def includes_framework(self, framework: str) -> bool:
        return not self.frameworks or framework in self.frameworks

    def to_query(self) -> str:
        parts = []
        if self.models:
            parts.append(f"models={','.join(self.models)}")
        if self.temps:
            parts.append(f"temps={','.join(self.temps)}")
        if self.dataset != "all":
            parts.append(f"dataset={self.dataset}")
        if self.frameworks:
            parts.append(f"frameworks={','.join(self.frameworks)}")
        return "&".join(parts)


def parse_filter_params(
    params: dict[str, str],
    catalog: dict,
) -> FilterState:
    all_models = catalog.get("models") or []
    all_temps = catalog.get("temps") or []
    all_fw = catalog.get("frameworks") or []
    all_ds = catalog.get("datasets") or []

    models_raw = _split_csv(params.get("models", ""))
    temps_raw = _split_csv(params.get("temps", ""))
    fw_raw = _split_csv(params.get("frameworks", ""))
    dataset = params.get("dataset", "all") or "all"

    models = [m for m in (models_raw or all_models) if m in all_models]
    temps = [t for t in (temps_raw or all_temps) if t in all_temps]
    frameworks = [f for f in (fw_raw or all_fw) if f in all_fw]

    if dataset != "all" and dataset not in all_ds:
        dataset = "all"

    return FilterState(
        models=models or all_models,
        temps=temps or all_temps,
        dataset=dataset,
        frameworks=frameworks or all_fw,
    )


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]
