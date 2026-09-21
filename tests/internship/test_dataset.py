import json

import pytest

from app.systems.internship.dataset import (
    DATASET_VERSION,
    EXPECTED_RECOMMENDATION_COUNTS,
    InternshipDatasetError,
    load_dataset,
    validate_cases,
)


def test_dataset_has_exact_balanced_synthetic_cases():
    cases = load_dataset()
    counts = {}
    for case in cases:
        label = case.expected_output["recommendation"]
        counts[label] = counts.get(label, 0) + 1

    assert len(cases) == 25
    assert [case.id for case in cases] == [
        f"internship-application-{index:03d}" for index in range(1, 26)
    ]
    assert len({case.id for case in cases}) == 25
    assert {case.system for case in cases} == {"internship-coordinator"}
    assert {case.metadata["dataset_version"] for case in cases} == {
        DATASET_VERSION
    }
    assert all(case.metadata["synthetic"] is True for case in cases)
    assert counts == EXPECTED_RECOMMENDATION_COUNTS


def test_dataset_rejects_duplicate_ids():
    raw = {
        "id": "duplicate",
        "system": "internship-coordinator",
        "input": {},
        "expected_output": {"recommendation": "APPROVE"},
        "metadata": {"dataset_version": DATASET_VERSION, "synthetic": True},
    }

    with pytest.raises(InternshipDatasetError, match="duplicate"):
        validate_cases([raw, raw])


def test_dataset_rejects_wrong_system_version_and_non_synthetic():
    raw = {
        "id": "bad",
        "system": "wrong",
        "input": {},
        "expected_output": {"recommendation": "APPROVE"},
        "metadata": {"dataset_version": "wrong", "synthetic": False},
    }

    with pytest.raises(InternshipDatasetError, match="invalid system"):
        validate_cases([raw])

    raw["system"] = "internship-coordinator"
    with pytest.raises(InternshipDatasetError, match="dataset version"):
        validate_cases([raw])

    raw["metadata"]["dataset_version"] = DATASET_VERSION
    with pytest.raises(InternshipDatasetError, match="not marked synthetic"):
        validate_cases([raw])


def test_dataset_file_round_trips_as_json():
    cases = load_dataset()
    assert json.loads(json.dumps([case.model_dump() for case in cases]))