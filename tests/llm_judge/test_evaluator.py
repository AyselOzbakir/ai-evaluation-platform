from app.core.models import EvaluationCase, SystemOutput
from app.evaluators.llm_judge.client import JudgeResponse
from app.evaluators.llm_judge.evaluator import LLMJudgeEvaluator, build_prompt
from app.evaluators.llm_judge.rubric import Rubric


class FakeJudgeClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def judge(self, prompt):
        self.prompts.append(prompt)
        return self.response


def rubric():
    return Rubric(
        name="generic_correctness",
        prompt_version="generic-v1",
        pass_threshold=0.7,
        criteria="Compare actual output with expected output.",
        fields={
            "input": ["question", "missing_input"],
            "expected": ["answer"],
            "actual": ["answer"],
            "context": ["citations", "missing_context"],
        },
    )


def case():
    return EvaluationCase(
        id="case-1",
        system="synthetic-system",
        input={"question": "What is two plus two?"},
        expected_output={"answer": "4"},
    )


def output():
    return SystemOutput(
        output={"answer": "4"},
        metadata={"citations": ["synthetic-source"]},
    )


def test_prompt_contains_selected_values_and_missing_fields_as_null():
    prompt = build_prompt(rubric(), case(), output())

    assert '"question":"What is two plus two?"' in prompt
    assert '"missing_input":null' in prompt
    assert '"answer":"4"' in prompt
    assert '"citations":["synthetic-source"]' in prompt
    assert '"missing_context":null' in prompt
    assert "generic_correctness" in prompt
    assert "generic-v1" in prompt
    assert "Compare actual output with expected output." in prompt


def test_prompt_generation_is_deterministic():
    first = build_prompt(rubric(), case(), output())
    second = build_prompt(rubric(), case(), output())

    assert first == second


def test_evaluator_calls_client_once_and_passes_by_threshold():
    client = FakeJudgeClient(JudgeResponse(score=0.8, reason="Strong match."))
    evaluator = LLMJudgeEvaluator(
        rubric(), client, model_name="synthetic-model", provider="fake"
    )

    result = evaluator.evaluate(case(), output())

    assert len(client.prompts) == 1
    assert result.evaluator == "generic_correctness"
    assert result.score == 0.8
    assert result.passed is True
    assert result.reason == "Strong match."
    assert result.metadata == {
        "rubric": "generic_correctness",
        "prompt_version": "generic-v1",
        "model": "synthetic-model",
        "provider": "fake",
        "pass_threshold": 0.7,
    }


def test_evaluator_fails_below_threshold():
    client = FakeJudgeClient(JudgeResponse(score=0.6, reason="Weak match."))
    result = LLMJudgeEvaluator(rubric(), client).evaluate(case(), output())

    assert result.passed is False
    assert result.score == 0.6


def test_explicit_passed_value_overrides_threshold():
    client = FakeJudgeClient(
        JudgeResponse(score=0.95, reason="Explicit failure.", passed=False)
    )
    result = LLMJudgeEvaluator(rubric(), client).evaluate(case(), output())

    assert result.passed is False


def test_explicit_passed_true_overrides_low_score():
    client = FakeJudgeClient(
        JudgeResponse(score=0.1, reason="Explicit pass.", passed=True)
    )
    result = LLMJudgeEvaluator(rubric(), client).evaluate(case(), output())

    assert result.passed is True


def test_invalid_score_from_client_is_rejected():
    class MalformedClient:
        def judge(self, prompt):
            return type("Response", (), {"score": 2, "reason": "bad", "passed": None})()

    evaluator = LLMJudgeEvaluator(rubric(), MalformedClient())

    try:
        evaluator.evaluate(case(), output())
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("invalid judge score was accepted")