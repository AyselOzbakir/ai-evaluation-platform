"""Dataset format checks: unit tests for the validator + a check of real dataset files."""

import json
from pathlib import Path

import pytest

from app.systems.ata_rag.dataset import category_counts, validate_cases

DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets" / "ata_rag"


def good_case(**overrides):
    case = {
        "id": "ata-001",
        "system": "ata-rag",
        "input": {"question": "Q?", "language": "en"},
        "expected_output": {"answer": "A", "sources": ["https://akademiata.pl/x"]},
        "metadata": {"category": "factual", "difficulty": "easy"},
    }
    case.update(overrides)
    return case


def test_valid_case_has_no_problems():
    cases, problems = validate_cases([good_case()])
    assert problems == [] and len(cases) == 1


def test_valid_no_answer_case():
    case = good_case(
        id="ata-002",
        expected_output={"no_answer": True},
        metadata={"category": "no_answer"},
    )
    _, problems = validate_cases([case])
    assert problems == []


def test_duplicate_ids_are_reported():
    _, problems = validate_cases([good_case(), good_case()])
    assert any("duplicate id" in p for p in problems)


def test_bad_category_language_and_system_are_reported():
    case = good_case(
        system="other",
        input={"question": "Q?", "language": "de"},
        metadata={"category": "weird"},
    )
    _, problems = validate_cases([case])
    joined = " ".join(problems)
    assert "system must be" in joined and "language" in joined and "category" in joined


def test_factual_case_without_sources_is_reported():
    case = good_case(expected_output={"answer": "A"})
    _, problems = validate_cases([case])
    assert any("needs expected_output.sources" in p for p in problems)


def test_no_answer_case_must_set_flag():
    case = good_case(expected_output={}, metadata={"category": "no_answer"})
    _, problems = validate_cases([case])
    assert any("no_answer = true" in p for p in problems)


def test_relative_source_urls_are_reported():
    case = good_case(expected_output={"answer": "A", "sources": ["/admissions"]})
    _, problems = validate_cases([case])
    assert any("http" in p for p in problems)


def test_invalid_case_shape_is_reported_without_crashing():
    cases, problems = validate_cases([{"id": "broken"}])
    assert cases == [] and problems


def test_category_counts():
    cases, _ = validate_cases([good_case(), good_case(id="ata-002")])
    assert category_counts(cases) == {"factual": 2}


@pytest.mark.parametrize("path", sorted(DATASET_DIR.glob("*.json")), ids=lambda p: p.name)
def test_real_dataset_files_are_valid(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    _, problems = validate_cases(raw)
    assert problems == []
