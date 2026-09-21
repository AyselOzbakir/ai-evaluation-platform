"""Validation helpers for the ATA golden dataset (``datasets/ata_rag/``).

Run from the repo root to check a dataset file and see the category counts::

    python -m app.systems.ata_rag.dataset datasets/ata_rag/ata-rag-v1.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.models import EvaluationCase

SYSTEM_NAME = "ata-rag"
DATASET_VERSION = "ata-rag-v1"
EXPECTED_CASE_COUNT = 100
STABLE_ID_PATTERN = re.compile(r"^ata-rag-\d{3}$")
VALID_CATEGORIES = {
    "factual_answer",
    "multi_source",
    "no_answer",
    "citation_required",
    "partial_relevance",
    "distractor_sources",
    "ambiguous_query",
    "exact_source_match",
    "missing_source",
    "edge_case",
}
CATEGORIES_REQUIRING_SOURCES = VALID_CATEGORIES - {"no_answer"}
VALID_LANGUAGES = {"en", "pl"}


def validate_cases(
    raw_cases: list[dict[str, Any]],
    require_full_dataset: bool = False,
) -> tuple[list[EvaluationCase], list[str]]:
    """Parse raw dicts into ``EvaluationCase`` objects and return (cases, problems)."""
    cases: list[EvaluationCase] = []
    problems: list[str] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_cases):
        label = f"#{index} ({raw.get('id', 'no id') if isinstance(raw, dict) else 'not an object'})"
        try:
            case = EvaluationCase.model_validate(raw)
        except ValidationError as exc:
            problems.append(f"{label}: invalid case format: {exc.errors()[0]['msg']}")
            continue

        if case.id in seen_ids:
            problems.append(f"{label}: duplicate id")
        seen_ids.add(case.id)

        if not STABLE_ID_PATTERN.fullmatch(case.id):
            problems.append(f"{label}: id must match ata-rag-NNN")

        if case.system != SYSTEM_NAME:
            problems.append(f"{label}: system must be '{SYSTEM_NAME}'")

        if case.metadata.get("dataset_version") != DATASET_VERSION:
            problems.append(
                f"{label}: metadata.dataset_version must be '{DATASET_VERSION}'"
            )
        if case.metadata.get("synthetic") is not True:
            problems.append(f"{label}: metadata.synthetic must be true")
        if case.metadata.get("split") != "golden":
            problems.append(f"{label}: metadata.split must be 'golden'")

        question = case.input.get("question")
        if not isinstance(question, str) or not question.strip():
            problems.append(f"{label}: input.question is missing or empty")
        language = case.input.get("language")
        if language is not None and language not in VALID_LANGUAGES:
            problems.append(f"{label}: input.language must be one of {sorted(VALID_LANGUAGES)}")

        category = case.metadata.get("category")
        if category not in VALID_CATEGORIES:
            problems.append(f"{label}: metadata.category must be one of {sorted(VALID_CATEGORIES)}")

        sources = case.expected_output.get("sources") or []
        if not all(isinstance(s, str) and s.startswith("http") for s in sources):
            problems.append(f"{label}: expected_output.sources must be full http(s) URLs")

        if category == "no_answer":
            if case.expected_output.get("no_answer") is not True:
                problems.append(f"{label}: no_answer cases need expected_output.no_answer = true")
        else:
            if not (case.expected_output.get("answer") or sources):
                problems.append(f"{label}: needs expected_output.answer and/or sources")
            if category in CATEGORIES_REQUIRING_SOURCES and not sources:
                problems.append(f"{label}: category '{category}' needs expected_output.sources")

        cases.append(case)

    if require_full_dataset:
        if len(cases) < EXPECTED_CASE_COUNT:
            problems.append(
                f"dataset must contain at least {EXPECTED_CASE_COUNT} cases; found {len(cases)}"
            )
        if len(cases) != EXPECTED_CASE_COUNT:
            problems.append(
                f"dataset must contain exactly {EXPECTED_CASE_COUNT} cases; found {len(cases)}"
            )
        expected_ids = {
            f"ata-rag-{index:03d}"
            for index in range(1, EXPECTED_CASE_COUNT + 1)
        }
        if set(seen_ids) != expected_ids:
            problems.append("dataset IDs must be exactly ata-rag-001 through ata-rag-100")

    return cases, problems


def category_counts(cases: list[EvaluationCase]) -> dict[str, int]:
    return dict(Counter(c.metadata.get("category", "unknown") for c in cases))


def load_dataset(path: str | Path) -> list[EvaluationCase]:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"Dataset file not found: {file_path}")
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Dataset must be a JSON array: {file_path}")
    cases, problems = validate_cases(raw, require_full_dataset=True)
    if problems:
        raise ValueError(f"{file_path}: " + "; ".join(problems))
    return cases


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python -m app.systems.ata_rag.dataset <dataset.json>")
        return 2
    raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("Dataset must be a JSON array of cases.")
        return 2
    cases, problems = validate_cases(raw, require_full_dataset=True)
    print(f"Cases: {len(cases)}")
    for category, count in sorted(category_counts(cases).items()):
        print(f"  {category}: {count}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nNo problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
