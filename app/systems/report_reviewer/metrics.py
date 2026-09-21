"""Pure classification metrics for report-reviewer decisions."""

from __future__ import annotations

from collections.abc import Sequence


def classification_report(
    expected: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
) -> dict:
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted must have equal lengths")

    ordered_labels = list(labels)
    if len(set(ordered_labels)) != len(ordered_labels):
        raise ValueError("labels must be unique")
    allowed = set(ordered_labels)
    unknown = (set(expected) | set(predicted)) - allowed
    if unknown:
        raise ValueError(f"unknown labels: {sorted(unknown)}")

    index = {label: position for position, label in enumerate(ordered_labels)}
    matrix = [[0 for _ in ordered_labels] for _ in ordered_labels]
    for expected_label, predicted_label in zip(expected, predicted):
        matrix[index[expected_label]][index[predicted_label]] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []
    correct = 0

    for position, label in enumerate(ordered_labels):
        true_positive = matrix[position][position]
        predicted_total = sum(row[position] for row in matrix)
        expected_total = sum(matrix[position])
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / expected_total if expected_total else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": expected_total,
        }
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
        correct += true_positive

    total = len(expected)
    return {
        "labels": ordered_labels,
        "confusion_matrix": matrix,
        "per_class": per_class,
        "macro_precision": _mean(precisions),
        "macro_recall": _mean(recalls),
        "macro_f1": _mean(f1_scores),
        "accuracy": correct / total if total else 0.0,
    }


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0