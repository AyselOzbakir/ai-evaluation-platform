import pytest

from app.systems.report_reviewer.metrics import classification_report

LABELS = ["APPROVED", "NEEDS_REVIEW", "REJECTED"]


def test_perfect_classification():
    result = classification_report(
        ["APPROVED", "NEEDS_REVIEW", "REJECTED"],
        ["APPROVED", "NEEDS_REVIEW", "REJECTED"],
        LABELS,
    )

    assert result["confusion_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0


def test_mixed_classification_and_matrix_placement():
    result = classification_report(
        ["APPROVED", "APPROVED", "NEEDS_REVIEW", "REJECTED"],
        ["APPROVED", "REJECTED", "NEEDS_REVIEW", "APPROVED"],
        LABELS,
    )

    assert result["confusion_matrix"] == [[1, 0, 1], [0, 1, 0], [1, 0, 0]]
    assert result["per_class"]["APPROVED"]["support"] == 2
    assert result["accuracy"] == 0.5


def test_missing_predicted_class_uses_zero_division_values():
    result = classification_report(
        ["APPROVED", "REJECTED"],
        ["APPROVED", "APPROVED"],
        LABELS,
    )

    rejected = result["per_class"]["REJECTED"]
    assert rejected["precision"] == 0.0
    assert rejected["recall"] == 0.0
    assert rejected["f1"] == 0.0


def test_empty_inputs_are_deterministic():
    result = classification_report([], [], LABELS)

    assert result["confusion_matrix"] == [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    assert result["accuracy"] == 0.0
    assert result["macro_f1"] == 0.0


def test_unknown_labels_are_rejected():
    with pytest.raises(ValueError, match="unknown labels"):
        classification_report(["APPROVED"], ["UNKNOWN"], LABELS)


def test_unequal_lengths_are_rejected():
    with pytest.raises(ValueError, match="equal lengths"):
        classification_report(["APPROVED"], [], LABELS)