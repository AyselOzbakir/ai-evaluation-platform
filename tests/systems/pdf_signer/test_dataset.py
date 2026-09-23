import json

import pytest

from app.systems.pdf_signer.dataset import (
    DATASET_VERSION,
    PDFSignerDatasetError,
    load_dataset,
    validate_cases,
)


def test_golden_dataset_has_15_stable_synthetic_cases():
    cases = load_dataset()

    assert len(cases) == 15
    assert [case.id for case in cases] == [
        f"pdf-signer-{index:03d}" for index in range(1, 16)
    ]
    assert len({case.id for case in cases}) == 15
    assert {case.system for case in cases} == {"pdf-signer"}
    assert {case.metadata["dataset_version"] for case in cases} == {DATASET_VERSION}
    assert all(case.metadata["synthetic"] is True for case in cases)
    assert {case.input["operation"] for case in cases} == {"detect", "place"}


def test_dataset_rejects_duplicate_ids():
    raw = {
        "id": "same",
        "system": "pdf-signer",
        "input": {"operation": "detect"},
        "metadata": {"dataset_version": DATASET_VERSION, "synthetic": True},
    }

    with pytest.raises(PDFSignerDatasetError, match="duplicate"):
        validate_cases([raw, raw])


def test_dataset_rejects_wrong_system_version_and_non_synthetic():
    raw = {
        "id": "bad",
        "system": "wrong",
        "input": {"operation": "detect"},
        "metadata": {"dataset_version": "wrong", "synthetic": False},
    }

    with pytest.raises(PDFSignerDatasetError, match="invalid system"):
        validate_cases([raw])

    raw["system"] = "pdf-signer"
    with pytest.raises(PDFSignerDatasetError, match="dataset version"):
        validate_cases([raw])

    raw["metadata"]["dataset_version"] = DATASET_VERSION
    with pytest.raises(PDFSignerDatasetError, match="not marked synthetic"):
        validate_cases([raw])


def test_dataset_rejects_invalid_operation():
    raw = {
        "id": "bad-op",
        "system": "pdf-signer",
        "input": {"operation": "sign"},
        "metadata": {"dataset_version": DATASET_VERSION, "synthetic": True},
    }

    with pytest.raises(PDFSignerDatasetError, match="invalid operation"):
        validate_cases([raw])


def test_dataset_file_round_trips_as_json():
    cases = load_dataset()
    assert json.loads(json.dumps([case.model_dump() for case in cases]))
