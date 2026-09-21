"""Application-level evaluation execution."""

from app.core.config import RunConfig
from app.core.experiment import ExperimentResult
from app.core.registry import Registry
from app.integrations.langfuse.runner import run_experiment_with_langfuse


def run_configured_experiment(
    config: RunConfig,
    registry: Registry,
) -> ExperimentResult:
    return run_experiment_with_langfuse(config, registry)