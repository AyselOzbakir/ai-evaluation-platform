from app.core.models import EvaluationCase, SystemOutput
from app.evaluators.llm_judge.client import JudgeResponse
from app.systems.internship.judge import default_judge_evaluators


class FakeJudgeClient:
    def judge(self, prompt: str) -> JudgeResponse:
        return JudgeResponse(score=0.9, reason="Synthetic judge result.")


def test_internship_judge_factory_loads_all_rubrics():
    evaluators = default_judge_evaluators(
        FakeJudgeClient(), model_name="fake-model", provider="fake"
    )

    assert [evaluator.name for evaluator in evaluators] == [
        "decision_correctness",
        "explanation_quality",
        "hallucination_detection",
    ]
    assert [evaluator.rubric.pass_threshold for evaluator in evaluators] == [
        0.7,
        0.6,
        0.7,
    ]


def test_internship_judge_factory_uses_generic_evaluator_with_fake_client():
    evaluator = default_judge_evaluators(FakeJudgeClient())[0]
    case = EvaluationCase(
        id="internship-application-001",
        system="internship-coordinator",
        input={
            "pdf_path": "synthetic/valid/application-001.pdf",
            "student_email": "synthetic-001@example.test",
        },
        expected_output={"recommendation": "APPROVE"},
    )
    output = SystemOutput(
        output={
            "system": "internship-coordinator",
            "recommendation": "APPROVE",
            "external_decision": "PENDING",
            "notes": "RECOMMENDATION: APPROVE\n[OK] Ready. [PASS] Valid.",
            "case_id": "synthetic-case-001",
        }
    )

    result = evaluator.evaluate(case, output)

    assert result.evaluator == "decision_correctness"
    assert result.score == 0.9
    assert result.passed is True
