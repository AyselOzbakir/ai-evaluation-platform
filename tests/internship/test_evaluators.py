from app.core.models import EvaluationCase, SystemOutput
from app.systems.internship.evaluators import (
    CoordinatorDecisionEvaluator,
    CoordinatorEvidenceEvaluator,
    CoordinatorSchemaEvaluator,
)


def case(expected_output=None):
    return EvaluationCase(
        id="internship-001",
        system="internship-coordinator",
        input={},
        expected_output=expected_output or {},
    )


def output(**values):
    result = {
        "system": "internship-coordinator",
        "recommendation": "APPROVE",
        "external_decision": "PENDING",
        "notes": "RECOMMENDATION: APPROVE\n[OK] Ready. [PASS] Valid.",
        "case_id": "synthetic-case-001",
    }
    result.update(values)
    return SystemOutput(output=result)


def test_decision_evaluator_passes_and_fails():
    evaluator = CoordinatorDecisionEvaluator()

    passed = evaluator.evaluate(case({"recommendation": "APPROVE"}), output())
    failed = evaluator.evaluate(case({"recommendation": "REJECT"}), output())

    assert passed.passed is True and passed.score == 1.0
    assert failed.passed is False and failed.score == 0.0


def test_schema_evaluator_accepts_valid_output():
    result = CoordinatorSchemaEvaluator().evaluate(case(), output())

    assert result.passed is True
    assert result.score == 1.0


def test_schema_evaluator_rejects_invalid_output():
    result = CoordinatorSchemaEvaluator().evaluate(
        case(), output(recommendation="PENDING", external_decision="APPROVE")
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "recommendation is invalid" in result.reason


def test_evidence_evaluator_perfect_match():
    result = CoordinatorEvidenceEvaluator().evaluate(
        case({"evidence_markers": ["[OK]", "[PASS]"]}),
        output(),
    )

    assert result.passed is True
    assert result.score == 1.0


def test_evidence_evaluator_partial_match():
    result = CoordinatorEvidenceEvaluator().evaluate(
        case({"evidence_markers": ["[OK]", "[MISSING]"]}),
        output(),
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.metadata["missing"] == ["[MISSING]"]


def test_evidence_evaluator_without_markers_is_neutral():
    result = CoordinatorEvidenceEvaluator().evaluate(case(), output())

    assert result.passed is True
    assert result.score is None
    assert result.metadata["skipped"] is True