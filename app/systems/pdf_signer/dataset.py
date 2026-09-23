"""Validation and loading helpers for the synthetic PDF Signer dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.models import EvaluationCase

SYSTEM_NAME = "pdf-signer"
DATASET_VERSION = "pdf-signer-v1"
ALLOWED_OPERATIONS = {"detect", "place"}
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "pdf_signer"
    / "pdf-signer-v1.json"
)


class PDFSignerDatasetError(ValueError):
    pass


def load_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> list[EvaluationCase]:
    file_path = Path(path)
    if not file_path.exists():
        raise PDFSignerDatasetError(f"Dataset file not found: {file_path}")
    try:
        raw_cases: Any = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PDFSignerDatasetError(f"{file_path}: invalid JSON: {exc}") from exc
    return validate_cases(raw_cases, file_path=file_path)


def validate_cases(
    raw_cases: Any,
    file_path: str | Path = "dataset",
) -> list[EvaluationCase]:
    if not isinstance(raw_cases, list):
        raise PDFSignerDatasetError(f"{file_path}: expected a JSON array of cases")

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        try:
            case = EvaluationCase.model_validate(raw_case)
        except ValidationError as exc:
            raise PDFSignerDatasetError(
                f"{file_path}: invalid case at index {index}: {exc}"
            ) from exc
        if case.id in seen_ids:
            raise PDFSignerDatasetError(f"{file_path}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)
        if case.system != SYSTEM_NAME:
            raise PDFSignerDatasetError(f"{file_path}: case {case.id!r} has invalid system")
        if case.metadata.get("dataset_version") != DATASET_VERSION:
            raise PDFSignerDatasetError(
                f"{file_path}: case {case.id!r} has invalid dataset version"
            )
        if case.metadata.get("synthetic") is not True:
            raise PDFSignerDatasetError(
                f"{file_path}: case {case.id!r} is not marked synthetic"
            )
        operation = case.input.get("operation")
        if operation not in ALLOWED_OPERATIONS:
            raise PDFSignerDatasetError(
                f"{file_path}: case {case.id!r} has invalid operation {operation!r}"
            )
        cases.append(case)

    return cases
