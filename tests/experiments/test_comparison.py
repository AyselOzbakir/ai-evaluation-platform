from app.core.experiment import (
    CaseResult,
    ExperimentResult,
)
from app.core.models import EvaluationResult
from app.experiments.comparison import (
    MetricRule,
    compare_experiments,
)


def make_case(
    case_id: str,
    passed: bool,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        evaluations=[
            EvaluationResult(
                evaluator="correctness",
                score=0.9 if passed else 0.4,
                passed=passed,
                reason="test result",
            )
        ],
    )


def test_detects_regression_and_new_failure():
    baseline = ExperimentResult(
        experiment_id="baseline-v1",
        system="ata-rag",
        dataset_version="golden-v1",
        application_version="v1",
        started_at="2026-09-17T00:00:00Z",
        case_results=[
            make_case("case-1", True),
            make_case("case-2", True),
        ],
        aggregate_metrics={
            "correctness_avg_score": 0.91,
        },
        passed=True,
    )

    candidate = ExperimentResult(
        experiment_id="candidate-v2",
        system="ata-rag",
        dataset_version="golden-v1",
        application_version="v2",
        started_at="2026-09-17T01:00:00Z",
        case_results=[
            make_case("case-1", True),
            make_case("case-2", False),
        ],
        aggregate_metrics={
            "correctness_avg_score": 0.86,
        },
        passed=True,
    )

    rules = {
        "correctness_avg_score": MetricRule(
            direction="higher",
            minimum=0.90,
            max_regression=0.02,
        )
    }

    result = compare_experiments(
        baseline,
        candidate,
        rules,
    )

    assert result.passed is False

    assert (
        result.metrics[0].status
        == "regressed"
    )

    assert result.newly_failed_cases == [
        "case-2"
    ]