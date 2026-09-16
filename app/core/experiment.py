"""Experiment result shape. Stable contract Person 5 reads for comparison/UI - do not rename fields."""

from typing import Any

from pydantic import BaseModel, Field

from app.core.models import EvaluationResult, SystemOutput


class CaseResult(BaseModel):
    case_id: str
    output: SystemOutput | None = None
    evaluations: list[EvaluationResult] = Field(default_factory=list)
    error: str | None = None


class ExperimentResult(BaseModel):
    experiment_id: str
    system: str
    dataset_version: str
    application_version: str
    started_at: str
    case_results: list[CaseResult] = Field(default_factory=list)
    aggregate_metrics: dict[str, float] = Field(default_factory=dict)
    passed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
