"""YAML configuration loader for evaluation runs.

Example (see configs/example.yaml):

    system: ata-rag
    dataset_version: ata-rag-golden-v1
    dataset_path: datasets/ata_rag/golden_v1.json
    application_version: git-sha-or-label
    evaluators:
      - retrieval_recall
      - answer_correctness
    thresholds:
      answer_correctness: 0.90
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class ConfigError(ValueError):
    pass


class RunConfig(BaseModel):
    system: str
    dataset_version: str
    dataset_path: str
    application_version: str = "unknown"
    evaluators: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)


def load_run_config(path: str | Path) -> RunConfig:
    file_path = Path(path)
    if not file_path.exists():
        raise ConfigError(f"Config file not found: {file_path}")

    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{file_path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{file_path}: expected a YAML mapping at the top level")

    try:
        return RunConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"{file_path}: invalid run config: {exc}") from exc
