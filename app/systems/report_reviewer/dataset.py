"""Validation and loading helpers for the synthetic report-reviewer dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.models import EvaluationCase

SYSTEM_NAME = "report-reviewer"
DATASET_VERSION = "report-reviewer-v1"
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "report_reviewer"
    / "report-reviewer-v1.json"
)


class ReportReviewerDatasetError(ValueError):
    pass


def load_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> list[EvaluationCase]:
    file_path = Path(path)
    if not file_path.exists():
        raise ReportReviewerDatasetError(f"Dataset file not found: {file_path}")
    try:
        raw_cases: Any = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportReviewerDatasetError(
            f"{file_path}: invalid JSON: {exc}"
        ) from exc
    return validate_cases(raw_cases, file_path=file_path)


def validate_cases(
    raw_cases: Any,
    file_path: str | Path = "dataset",
) -> list[EvaluationCase]:
    if not isinstance(raw_cases, list):
        raise ReportReviewerDatasetError(
            f"{file_path}: expected a JSON array of cases"
        )

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        try:
            case = EvaluationCase.model_validate(raw_case)
        except ValidationError as exc:
            raise ReportReviewerDatasetError(
                f"{file_path}: invalid case at index {index}: {exc}"
            ) from exc
        if case.id in seen_ids:
            raise ReportReviewerDatasetError(
                f"{file_path}: duplicate case id {case.id!r}"
            )
        seen_ids.add(case.id)
        if case.system != SYSTEM_NAME:
            raise ReportReviewerDatasetError(
                f"{file_path}: case {case.id!r} has invalid system"
            )
        if case.metadata.get("dataset_version") != DATASET_VERSION:
            raise ReportReviewerDatasetError(
                f"{file_path}: case {case.id!r} has invalid dataset version"
            )
        if case.metadata.get("synthetic") is not True:
            raise ReportReviewerDatasetError(
                f"{file_path}: case {case.id!r} is not marked synthetic"
            )
        cases.append(case)

    return cases