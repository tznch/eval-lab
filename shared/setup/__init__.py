"""Dashboard setup: readiness checks and eval launch."""

from shared.setup.readiness import check_readiness
from shared.setup.model_endpoint import resolve_model_endpoint

__all__ = ["check_readiness", "resolve_model_endpoint"]
