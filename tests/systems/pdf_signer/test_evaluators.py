from app.core.models import EvaluationCase, SystemOutput
from app.systems.pdf_signer.evaluators import (
    PDFOutputEvaluator,
    SignatureCoordinateEvaluator,
    SignatureDetectionEvaluator,
)


def _case(expected_output: dict) -> EvaluationCase:
    return EvaluationCase(
        id="pdf-1",
        system="pdf_signer",
        input={},
        expected_output=expected_output,
    )


def test_signature_detection_passes_and_fails():
    evaluator = SignatureDetectionEvaluator()
    output = SystemOutput(output={"operation": "detect", "areas": [{"x": 1}]})

    passed = evaluator.evaluate(_case({"should_detect": True, "min_areas": 1}), output)
    failed = evaluator.evaluate(_case({"should_detect": True, "min_areas": 2}), output)

    assert passed.passed is True
    assert passed.score == 1.0
    assert failed.passed is False
    assert failed.score == 0.0


def test_signature_coordinate_evaluator_handles_tolerance():
    evaluator = SignatureCoordinateEvaluator()
    output = SystemOutput(
        output={"operation": "detect", "areas": [{"x": 105, "y": 98}]}
    )

    within = evaluator.evaluate(
        _case({"expected_area": {"x": 100, "y": 100, "tolerance": 6}}), output
    )
    outside = evaluator.evaluate(
        _case({"expected_area": {"x": 100, "y": 100, "tolerance": 4}}), output
    )

    assert within.passed is True
    assert within.metadata["best_distance"] < 6
    assert outside.passed is False


def test_pdf_output_evaluator_valid_and_missing_file(tmp_path):
    evaluator = PDFOutputEvaluator()
    valid_path = tmp_path / "signed.pdf"
    valid_path.write_bytes(b"pdf")

    valid = evaluator.evaluate(
        _case({}),
        SystemOutput(output={"operation": "place", "output_path": str(valid_path)}),
    )
    missing = evaluator.evaluate(
        _case({}),
        SystemOutput(
            output={"operation": "place", "output_path": str(tmp_path / "missing.pdf")}
        ),
    )

    assert valid.passed is True
    assert valid.score == 1.0
    assert missing.passed is False
    assert missing.score == 0.0


def test_evaluators_ignore_irrelevant_operations():
    output = SystemOutput(output={"operation": "place", "output_path": "x.pdf"})

    result = SignatureDetectionEvaluator().evaluate(_case({}), output)

    assert result.passed is False
    assert "requires a detect operation" in result.reason