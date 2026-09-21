"""Validation and loading helpers for the synthetic Coordinator dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.models import EvaluationCase

SYSTEM_NAME = "internship-coordinator"
DATASET_VERSION = "internship-coordinator-v1"
EXPECTED_CASE_COUNT = 25
EXPECTED_RECOMMENDATION_COUNTS = {
    "APPROVE": 9,
    "REQUEST CLARIFICATION": 8,
    "REJECT": 8,
}
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "internship"
    / "internship-coordinator-v1.json"
)


class InternshipDatasetError(ValueError):
    pass


def load_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> list[EvaluationCase]:
    file_path = Path(path)
    if not file_path.exists():
        raise InternshipDatasetError(f"Dataset file not found: {file_path}")
    try:
        raw_cases: Any = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InternshipDatasetError(f"{file_path}: invalid JSON: {exc}") from exc
    return validate_cases(raw_cases, file_path=file_path)


def validate_cases(
    raw_cases: Any,
    file_path: str | Path = "dataset",
) -> list[EvaluationCase]:
    if not isinstance(raw_cases, list):
        raise InternshipDatasetError(f"{file_path}: expected a JSON array of cases")

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        try:
            case = EvaluationCase.model_validate(raw_case)
        except ValidationError as exc:
            raise InternshipDatasetError(
                f"{file_path}: invalid case at index {index}: {exc}"
            ) from exc
        if case.id in seen_ids:
            raise InternshipDatasetError(f"{file_path}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)
        if case.system != SYSTEM_NAME:
            raise InternshipDatasetError(f"{file_path}: case {case.id!r} has invalid system")
        if case.metadata.get("dataset_version") != DATASET_VERSION:
            raise InternshipDatasetError(
                f"{file_path}: case {case.id!r} has invalid dataset version"
            )
        if case.metadata.get("synthetic") is not True:
            raise InternshipDatasetError(
                f"{file_path}: case {case.id!r} is not marked synthetic"
            )
        if case.expected_output.get("recommendation") not in EXPECTED_RECOMMENDATION_COUNTS:
            raise InternshipDatasetError(
                f"{file_path}: case {case.id!r} has invalid recommendation"
            )
        cases.append(case)

    if len(cases) != EXPECTED_CASE_COUNT:
        raise InternshipDatasetError(
            f"{file_path}: expected exactly {EXPECTED_CASE_COUNT} cases"
        )
    counts = {label: 0 for label in EXPECTED_RECOMMENDATION_COUNTS}
    for case in cases:
        counts[case.expected_output["recommendation"]] += 1
    if counts != EXPECTED_RECOMMENDATION_COUNTS:
        raise InternshipDatasetError(
            f"{file_path}: recommendation balance {counts} does not match "
            f"{EXPECTED_RECOMMENDATION_COUNTS}"
        )
    return cases