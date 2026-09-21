"""Classification metrics for Internship Coordinator recommendations."""

from collections.abc import Sequence

from app.systems.report_reviewer.metrics import classification_report

COORDINATOR_LABELS = ["APPROVE", "REQUEST CLARIFICATION", "REJECT"]

__all__ = ["COORDINATOR_LABELS", "classification_report"]


def coordinator_classification_report(
    expected: Sequence[str],
    predicted: Sequence[str],
) -> dict:
    return classification_report(expected, predicted, COORDINATOR_LABELS)