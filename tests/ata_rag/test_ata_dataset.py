"""Dataset format checks: unit tests for the validator + a check of real dataset files."""

import json
from pathlib import Path

import pytest

from app.systems.ata_rag.dataset import (
    DATASET_VERSION,
    category_counts,
    load_dataset,
    validate_cases,
)

DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets" / "ata_rag"


def good_case(**overrides):
    case = {
        "id": "ata-rag-001",
        "system": "ata-rag",
        "input": {"question": "Q?", "language": "en"},
        "expected_output": {"answer": "A", "sources": ["https://akademiata.pl/x"]},
        "metadata": {
            "category": "factual_answer",
            "difficulty": "easy",
            "dataset_version": DATASET_VERSION,
            "synthetic": True,
            "split": "golden",
        },
    }
    case.update(overrides)
    return case


def test_valid_case_has_no_problems():
    cases, problems = validate_cases([good_case()])
    assert problems == [] and len(cases) == 1


def test_valid_no_answer_case():
    case = good_case(
        id="ata-rag-002",
        expected_output={"no_answer": True},
        metadata={
            "category": "no_answer",
            "dataset_version": DATASET_VERSION,
            "synthetic": True,
            "split": "golden",
        },
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
        metadata={
            "category": "weird",
            "dataset_version": DATASET_VERSION,
            "synthetic": True,
            "split": "golden",
        },
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
    cases, _ = validate_cases([good_case(), good_case(id="ata-rag-002")])
    assert category_counts(cases) == {"factual_answer": 2}


def test_real_dataset_has_full_stable_synthetic_contract():
    cases = load_dataset(DATASET_DIR / "ata-rag-v1.json")

    assert len(cases) == 100
    assert [case.id for case in cases] == [
        f"ata-rag-{index:03d}" for index in range(1, 101)
    ]
    assert all(case.system == "ata-rag" for case in cases)
    assert all(case.metadata["dataset_version"] == DATASET_VERSION for case in cases)
    assert all(case.metadata["synthetic"] is True for case in cases)


@pytest.mark.parametrize("path", sorted(DATASET_DIR.glob("*.json")), ids=lambda p: p.name)
def test_real_dataset_files_are_valid(path):
    assert len(load_dataset(path)) == 100
