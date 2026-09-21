"""Rubric models and YAML loading for generic LLM-as-a-Judge evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_FIELD_GROUPS = {"input", "expected", "actual", "context"}


class Rubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    prompt_version: str
    pass_threshold: float
    criteria: str
    fields: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("name", "prompt_version", "criteria")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("pass_threshold")
    @classmethod
    def validate_threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("pass_threshold must be between 0 and 1")
        return value

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        unsupported = set(value) - SUPPORTED_FIELD_GROUPS
        if unsupported:
            raise ValueError(
                f"unsupported field groups: {sorted(unsupported)}"
            )
        for group, names in value.items():
            if not all(isinstance(name, str) and name.strip() for name in names):
                raise ValueError(f"fields.{group} must contain non-empty strings")
        return value


def load_rubric(path: str | Path, name: str | None = None) -> Rubric:
    """Load one rubric from either a single-rubric or rubrics-list YAML file."""
    rubric_path = Path(path)
    if not rubric_path.exists():
        raise ValueError(f"Rubric file not found: {rubric_path}")

    try:
        raw: Any = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid rubric YAML in {rubric_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Rubric file {rubric_path} must contain a mapping")

    candidate: Any = raw
    if isinstance(raw.get("rubrics"), list):
        rubrics = raw["rubrics"]
        if name is None:
            if len(rubrics) != 1:
                raise ValueError(
                    f"Rubric file {rubric_path} contains multiple rubrics; provide name"
                )
            candidate = rubrics[0]
        else:
            matches = [item for item in rubrics if isinstance(item, dict) and item.get("name") == name]
            if len(matches) != 1:
                raise ValueError(f"Rubric {name!r} not found in {rubric_path}")
            candidate = matches[0]
    elif name is not None and raw.get("name") != name:
        raise ValueError(f"Rubric {name!r} not found in {rubric_path}")

    try:
        return Rubric.model_validate(candidate)
    except Exception as exc:
        raise ValueError(f"Invalid rubric in {rubric_path}: {exc}") from exc