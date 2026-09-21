import json

import pytest

from app.systems.report_reviewer.dataset import (
    DATASET_VERSION,
    ReportReviewerDatasetError,
    load_dataset,
    validate_cases,
)


def test_golden_dataset_has_25_stable_synthetic_cases():
    cases = load_dataset()

    assert len(cases) == 25
    assert [case.id for case in cases] == [
        f"report-review-{index:03d}" for index in range(1, 26)
    ]
    assert len({case.id for case in cases}) == 25
    assert {case.system for case in cases} == {"report-reviewer"}
    assert {case.metadata["dataset_version"] for case in cases} == {
        DATASET_VERSION
    }
    assert all(case.metadata["synthetic"] is True for case in cases)
    assert {case.expected_output["status"] for case in cases} == {
        "APPROVED",
        "NEEDS_REVIEW",
        "REJECTED",
    }


def test_dataset_rejects_duplicate_ids():
    cases = [
        {
            "id": "same",
            "system": "report-reviewer",
            "input": {},
            "metadata": {
                "dataset_version": DATASET_VERSION,
                "synthetic": True,
            },
        }
    ]

    with pytest.raises(ReportReviewerDatasetError, match="duplicate"):
        validate_cases(cases + cases)


def test_dataset_rejects_wrong_system_version_and_non_synthetic():
    raw = {
        "id": "bad",
        "system": "wrong",
        "input": {},
        "metadata": {"dataset_version": "wrong", "synthetic": False},
    }

    with pytest.raises(ReportReviewerDatasetError, match="invalid system"):
        validate_cases([raw])

    raw["system"] = "report-reviewer"
    with pytest.raises(ReportReviewerDatasetError, match="dataset version"):
        validate_cases([raw])

    raw["metadata"]["dataset_version"] = DATASET_VERSION
    with pytest.raises(ReportReviewerDatasetError, match="not marked synthetic"):
        validate_cases([raw])


def test_dataset_file_is_valid_json():
    cases = load_dataset()
    assert json.loads(
        json.dumps([case.model_dump() for case in cases])
    )