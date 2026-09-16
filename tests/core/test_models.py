from app.core.models import EvaluationCase, EvaluationResult, SystemOutput


def test_evaluation_case_defaults():
    case = EvaluationCase(id="c1", system="fake", input={"q": "hi"})
    assert case.expected_output == {}
    assert case.metadata == {}


def test_system_output_defaults():
    output = SystemOutput(output={"a": 1})
    assert output.metadata == {}


def test_evaluation_result_optional_score():
    result = EvaluationResult(evaluator="e", passed=True)
    assert result.score is None
    assert result.reason == ""
