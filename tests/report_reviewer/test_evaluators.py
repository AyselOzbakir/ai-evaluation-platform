from app.core.models import EvaluationCase, SystemOutput
from app.systems.report_reviewer.evaluators import (
    ReportDecisionEvaluator,
    ReportFindingEvaluator,
    ReportSchemaEvaluator,
)


def case(expected_output):
    return EvaluationCase(
        id="review-001",
        system="report-reviewer",
        input={},
        expected_output=expected_output,
    )


def output(**values):
    base = {
        "system": "internship-report-reviewer",
        "status": "APPROVED",
        "score": 90,
        "summary": "Synthetic review.",
        "checks": [
            {
                "title": "Dates",
                "status": "PASS",
                "message": "Dates found.",
                "evidence": "Week 1.",
            }
        ],
        "engine": "RULES",
    }
    base.update(values)
    return SystemOutput(output=base)


def test_decision_evaluator_passes_and_fails():
    evaluator = ReportDecisionEvaluator()

    passed = evaluator.evaluate(case({"status": "APPROVED"}), output())
    failed = evaluator.evaluate(case({"status": "REJECTED"}), output())

    assert passed.passed is True
    assert passed.score == 1.0
    assert failed.passed is False
    assert failed.score == 0.0


def test_finding_evaluator_perfect_match():
    result = ReportFindingEvaluator().evaluate(
        case({"findings": {"Dates": "PASS"}}),
        output(),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["matched"] == ["Dates"]


def test_finding_evaluator_reports_missing_finding():
    result = ReportFindingEvaluator().evaluate(
        case({"findings": {"Dates": "PASS", "Signature": "WARNING"}}),
        output(),
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.metadata["missing"] == ["Signature"]


def test_finding_evaluator_reports_mismatched_finding():
    result = ReportFindingEvaluator().evaluate(
        case({"findings": {"Dates": "WARNING"}}),
        output(),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.metadata["mismatched"] == ["Dates"]


def test_schema_evaluator_accepts_valid_output():
    result = ReportSchemaEvaluator().evaluate(case({}), output())

    assert result.passed is True
    assert result.score == 1.0


def test_schema_evaluator_rejects_invalid_output():
    result = ReportSchemaEvaluator().evaluate(
        case({}),
        output(status="UNKNOWN", score=101),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "status is invalid" in result.reason