from app.core.models import EvaluationCase, SystemOutput
from app.evaluators.llm_judge.client import JudgeResponse
from app.systems.ata_rag.judge import default_judge_evaluators


class FakeJudgeClient:
    def judge(self, prompt: str) -> JudgeResponse:
        return JudgeResponse(score=0.9, reason="Synthetic judge result.")


def test_ata_judge_factory_loads_all_rubrics():
    evaluators = default_judge_evaluators(
        FakeJudgeClient(), model_name="fake-model", provider="fake"
    )

    assert [evaluator.name for evaluator in evaluators] == [
        "answer_correctness",
        "groundedness",
        "citation_source_correctness",
    ]
    assert [evaluator.rubric.pass_threshold for evaluator in evaluators] == [
        0.7,
        0.7,
        0.7,
    ]


def test_ata_judge_factory_uses_generic_evaluator_with_fake_client():
    evaluator = default_judge_evaluators(FakeJudgeClient())[0]
    case = EvaluationCase(
        id="ata-rag-001",
        system="ata-rag",
        input={"question": "Synthetic question"},
        expected_output={"answer": "Synthetic answer"},
    )
    output = SystemOutput(output={"answer": "Synthetic answer"})

    result = evaluator.evaluate(case, output)

    assert result.evaluator == "answer_correctness"
    assert result.score == 0.9
    assert result.passed is True