"""Deterministic evaluators for PDF Signer adapter outputs."""

import math
from pathlib import Path
from typing import Any

from app.core.models import EvaluationCase, EvaluationResult, Evaluator, SystemOutput


class SignatureDetectionEvaluator(Evaluator):
    name = "signature_detection"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        if output.output.get("operation") != "detect":
            return _irrelevant_result(self.name, "detect")

        areas = output.output.get("areas")
        if not isinstance(areas, list):
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="Detection output does not contain an areas list.",
            )

        expected = case.expected_output
        should_detect = expected.get("should_detect", True)
        min_areas = expected.get("min_areas", 1)
        if not isinstance(should_detect, bool) or not isinstance(min_areas, int):
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="Expected detection values must use a boolean should_detect and integer min_areas.",
            )

        area_count = len(areas)
        passed = (
            area_count >= min_areas
            if should_detect
            else area_count == 0
        )
        if should_detect:
            reason = (
                f"Detected {area_count} signature area(s); expected at least "
                f"{min_areas}."
            )
        else:
            reason = (
                f"Detected {area_count} signature area(s); expected no signature areas."
            )

        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=reason,
            metadata={"area_count": area_count},
        )


class SignatureCoordinateEvaluator(Evaluator):
    name = "signature_coordinates"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        if output.output.get("operation") != "detect":
            return _irrelevant_result(self.name, "detect")

        expected_area = case.expected_output.get("expected_area")
        if not isinstance(expected_area, dict):
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="Expected output does not contain expected_area coordinates.",
                metadata={"best_distance": None},
            )

        expected_x = expected_area.get("x")
        expected_y = expected_area.get("y")
        tolerance = expected_area.get("tolerance", 10.0)
        if not _is_number(expected_x) or not _is_number(expected_y):
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="expected_area must contain numeric x and y coordinates.",
                metadata={"best_distance": None},
            )
        if not _is_number(tolerance) or tolerance < 0:
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="expected_area tolerance must be a non-negative number.",
                metadata={"best_distance": None},
            )

        areas = output.output.get("areas", [])
        distances = [
            math.hypot(area["x"] - expected_x, area["y"] - expected_y)
            for area in areas
            if isinstance(area, dict)
            and _is_number(area.get("x"))
            and _is_number(area.get("y"))
        ]
        best_distance = min(distances, default=None)
        passed = best_distance is not None and best_distance <= tolerance
        if best_distance is None:
            reason = "No detected area contained numeric x and y coordinates."
        else:
            reason = (
                f"Closest detected area is {best_distance:.2f} units from the "
                f"expected coordinates; tolerance is {tolerance:.2f}."
            )

        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=reason,
            metadata={"best_distance": best_distance},
        )


class PDFOutputEvaluator(Evaluator):
    name = "pdf_output"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        if output.output.get("operation") != "place":
            return _irrelevant_result(self.name, "place")

        output_path = output.output.get("output_path")
        if not isinstance(output_path, str) or not output_path.strip():
            return _pdf_failure(self.name, "Place output does not contain an output path.")

        path = Path(output_path)
        if path.suffix.lower() != ".pdf":
            return _pdf_failure(self.name, "Output path does not have a .pdf extension.")
        if not path.is_file():
            return _pdf_failure(self.name, "Output path is not an existing regular file.")
        if path.stat().st_size <= 0:
            return _pdf_failure(self.name, "Output PDF file is empty.")

        return EvaluationResult(
            evaluator=self.name,
            score=1.0,
            passed=True,
            reason="Output is a non-empty PDF file.",
            metadata={"output_path": str(path)},
        )


def _irrelevant_result(name: str, operation: str) -> EvaluationResult:
    return EvaluationResult(
        evaluator=name,
        score=0.0,
        passed=False,
        reason=f"Evaluator requires a {operation} operation; output was ignored.",
    )


def _pdf_failure(name: str, reason: str) -> EvaluationResult:
    return EvaluationResult(
        evaluator=name,
        score=0.0,
        passed=False,
        reason=reason,
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)