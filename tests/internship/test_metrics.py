import pytest

from app.systems.internship.metrics import (
    COORDINATOR_LABELS,
    classification_report,
    coordinator_classification_report,
)


def test_perfect_classification():
    result = coordinator_classification_report(
        COORDINATOR_LABELS,
        COORDINATOR_LABELS,
    )

    assert result["labels"] == COORDINATOR_LABELS
    assert result["confusion_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert result["macro_f1"] == 1.0
    assert result["accuracy"] == 1.0


def test_mixed_classification_places_confusion_counts():
    result = classification_report(
        ["APPROVE", "APPROVE", "REQUEST CLARIFICATION", "REJECT"],
        ["APPROVE", "REJECT", "REQUEST CLARIFICATION", "APPROVE"],
        COORDINATOR_LABELS,
    )

    assert result["confusion_matrix"] == [[1, 0, 1], [0, 1, 0], [1, 0, 0]]
    assert result["accuracy"] == 0.5


def test_missing_predicted_class_uses_zero_division_values():
    result = classification_report(
        ["APPROVE", "REJECT"],
        ["APPROVE", "APPROVE"],
        COORDINATOR_LABELS,
    )

    assert result["per_class"]["REJECT"]["precision"] == 0.0
    assert result["per_class"]["REJECT"]["recall"] == 0.0
    assert result["per_class"]["REJECT"]["f1"] == 0.0


def test_empty_inputs_are_deterministic():
    result = classification_report([], [], COORDINATOR_LABELS)

    assert result["accuracy"] == 0.0
    assert result["macro_precision"] == 0.0
    assert result["macro_recall"] == 0.0
    assert result["macro_f1"] == 0.0


def test_unknown_labels_are_rejected():
    with pytest.raises(ValueError, match="unknown labels"):
        classification_report(["APPROVE"], ["UNKNOWN"], COORDINATOR_LABELS)


def test_unequal_lengths_are_rejected():
    with pytest.raises(ValueError, match="equal lengths"):
        classification_report(["APPROVE"], [], COORDINATOR_LABELS)