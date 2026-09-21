"""Application-level evaluation execution."""

from app.core.config import RunConfig
from app.core.experiment import ExperimentResult
from app.core.registry import Registry
from app.integrations.langfuse.runner import run_experiment_with_langfuse
from app.persistence.database import create_repository


def run_configured_experiment(
    config: RunConfig,
    registry: Registry,
) -> ExperimentResult:
    experiment = run_experiment_with_langfuse(config, registry)
    repository = create_repository()
    if repository is not None:
        repository.save_experiment(experiment)
    return experiment