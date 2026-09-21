"""Reads and writes experiment result JSON under the configured artifact directory."""

import os
from pathlib import Path

from app.core.experiment import ExperimentResult


class StorageError(ValueError):
    pass


def artifact_dir() -> Path:
    return Path(os.environ.get("EXPERIMENT_ARTIFACT_DIR", "artifacts/experiments"))


def save_experiment(experiment: ExperimentResult, directory: str | Path | None = None) -> Path:
    target_dir = Path(directory) if directory is not None else artifact_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{experiment.experiment_id}.json"
    with target_path.open("x", encoding="utf-8") as artifact_file:
        artifact_file.write(experiment.model_dump_json(indent=2))
    return target_path


def load_experiment(experiment_id: str, directory: str | Path | None = None) -> ExperimentResult:
    target_dir = Path(directory) if directory is not None else artifact_dir()
    target_path = target_dir / f"{experiment_id}.json"
    if not target_path.exists():
        raise StorageError(f"Experiment not found: {experiment_id}")
    return ExperimentResult.model_validate_json(target_path.read_text(encoding="utf-8"))


def list_experiments(directory: str | Path | None = None) -> list[str]:
    target_dir = Path(directory) if directory is not None else artifact_dir()
    if not target_dir.exists():
        return []
    return sorted(p.stem for p in target_dir.glob("*.json"))
