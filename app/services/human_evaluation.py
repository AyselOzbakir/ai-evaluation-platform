"""Human evaluation submission and persistence service."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.experiment import ExperimentResult
from app.core.storage import load_experiment
from app.persistence.database import DatabaseRepository, create_repository


class HumanEvaluationSubmission(BaseModel):
    experiment_id: str
    case_id: str
    evaluator_name: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    passed: bool | None = None
    label: str | None = None
    comment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_signal(self) -> "HumanEvaluationSubmission":
        if self.score is None and self.passed is None and not self.label:
            raise ValueError("At least one of score, passed, or label is required")
        return self


class HumanEvaluationResponse(HumanEvaluationSubmission):
    id: int
    created_at: datetime


def validate_target(submission: HumanEvaluationSubmission) -> ExperimentResult:
    experiment = load_experiment(submission.experiment_id)
    if not any(case.case_id == submission.case_id for case in experiment.case_results):
        raise ValueError(
            f"Case {submission.case_id!r} not found in experiment {submission.experiment_id!r}"
        )
    return experiment


def create_human_evaluation(
    submission: HumanEvaluationSubmission,
    repository: DatabaseRepository | None = None,
) -> HumanEvaluationResponse:
    validate_target(submission)
    created_at = datetime.now(UTC)
    payload = submission.model_dump()
    payload["created_at"] = created_at
    repository = repository or create_repository()
    if repository is not None:
        return HumanEvaluationResponse.model_validate(
            repository.add_human_evaluation(payload)
        )

    records = _read_fallback_records(submission.experiment_id)
    next_id = max((record["id"] for record in records), default=0) + 1
    payload = {"id": next_id, **payload}
    records.append(_json_safe(payload))
    _fallback_path(submission.experiment_id).parent.mkdir(parents=True, exist_ok=True)
    _fallback_path(submission.experiment_id).write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    return HumanEvaluationResponse.model_validate(payload)


def list_human_evaluations(
    experiment_id: str,
    repository: DatabaseRepository | None = None,
) -> list[HumanEvaluationResponse]:
    load_experiment(experiment_id)
    repository = repository or create_repository()
    if repository is not None:
        records = repository.list_human_evaluations(experiment_id)
    else:
        records = _read_fallback_records(experiment_id)
    return [HumanEvaluationResponse.model_validate(record) for record in records]


def _fallback_path(experiment_id: str) -> Path:
    artifact_dir = Path(os.environ.get("EXPERIMENT_ARTIFACT_DIR", "artifacts/experiments"))
    return artifact_dir.parent / "human_evaluations" / f"{experiment_id}.json"


def _read_fallback_records(experiment_id: str) -> list[dict[str, Any]]:
    path = _fallback_path(experiment_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=lambda value: value.isoformat()))