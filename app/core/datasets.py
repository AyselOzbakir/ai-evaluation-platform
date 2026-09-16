"""Dataset loading: a JSON array or JSONL file of EvaluationCase records."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.core.models import EvaluationCase


class DatasetError(ValueError):
    pass


def load_dataset(path: str | Path) -> list[EvaluationCase]:
    file_path = Path(path)
    if not file_path.exists():
        raise DatasetError(f"Dataset file not found: {file_path}")

    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        raise DatasetError(f"Dataset file is empty: {file_path}")

    if file_path.suffix == ".jsonl":
        raw_records = _parse_jsonl(text, file_path)
    else:
        raw_records = _parse_json_array(text, file_path)

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(raw_records):
        try:
            case = EvaluationCase.model_validate(record)
        except ValidationError as exc:
            raise DatasetError(f"{file_path}: invalid case at index {index}: {exc}") from exc
        if case.id in seen_ids:
            raise DatasetError(f"{file_path}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise DatasetError(f"Dataset file contains no cases: {file_path}")
    return cases


def _parse_json_array(text: str, file_path: Path) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{file_path}: invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise DatasetError(f"{file_path}: expected a JSON array of cases at the top level")
    return data


def _parse_jsonl(text: str, file_path: Path) -> list[dict]:
    records = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{file_path}: invalid JSON on line {line_no}: {exc}") from exc
    return records
