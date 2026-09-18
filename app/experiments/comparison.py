from typing import Literal

from pydantic import BaseModel, Field

from app.core.experiment import ExperimentResult


class MetricRule(BaseModel):
    direction: Literal["higher", "lower"] = "higher"
    minimum: float | None = None
    maximum: float | None = None
    max_regression: float | None = None


class MetricComparison(BaseModel):
    metric: str
    baseline: float
    candidate: float
    delta: float

    status: Literal[
        "improved",
        "regressed",
        "unchanged",
    ]

    passed: bool
    reason: str


class ExperimentComparison(BaseModel):
    baseline_id: str
    candidate_id: str
    system: str

    passed: bool

    metrics: list[MetricComparison] = Field(
        default_factory=list
    )

    newly_failed_cases: list[str] = Field(
        default_factory=list
    )

    resolved_cases: list[str] = Field(
        default_factory=list
    )


def _failed_case_ids(
    experiment: ExperimentResult,
) -> set[str]:
    failed: set[str] = set()

    for case in experiment.case_results:
        if case.error is not None:
            failed.add(case.case_id)
            continue

        if any(
            not evaluation.passed
            for evaluation in case.evaluations
        ):
            failed.add(case.case_id)

    return failed


def _compare_metric(
    metric: str,
    baseline: float,
    candidate: float,
    rule: MetricRule,
) -> MetricComparison:
    delta = candidate - baseline

    if abs(delta) < 1e-9:
        status = "unchanged"
    elif rule.direction == "higher":
        status = (
            "improved"
            if candidate > baseline
            else "regressed"
        )
    else:
        status = (
            "improved"
            if candidate < baseline
            else "regressed"
        )

    passed = True
    reasons: list[str] = []

    if (
        rule.minimum is not None
        and candidate < rule.minimum
    ):
        passed = False
        reasons.append(
            f"{candidate:.4f} is below minimum "
            f"{rule.minimum:.4f}."
        )

    if (
        rule.maximum is not None
        and candidate > rule.maximum
    ):
        passed = False
        reasons.append(
            f"{candidate:.4f} is above maximum "
            f"{rule.maximum:.4f}."
        )

    if rule.max_regression is not None:
        if rule.direction == "higher":
            regression = baseline - candidate
        else:
            regression = candidate - baseline

        if regression > rule.max_regression:
            passed = False
            reasons.append(
                f"Regression {regression:.4f} exceeds "
                f"allowed {rule.max_regression:.4f}."
            )

    if not reasons:
        if status == "improved":
            reasons.append("Metric improved.")
        elif status == "regressed":
            reasons.append(
                "Metric regressed but is within allowed limits."
            )
        else:
            reasons.append("Metric is unchanged.")

    return MetricComparison(
        metric=metric,
        baseline=baseline,
        candidate=candidate,
        delta=delta,
        status=status,
        passed=passed,
        reason=" ".join(reasons),
    )


def compare_experiments(
    baseline: ExperimentResult,
    candidate: ExperimentResult,
    rules: dict[str, MetricRule] | None = None,
) -> ExperimentComparison:
    if baseline.system != candidate.system:
        raise ValueError(
            "Experiments from different systems "
            "cannot be compared."
        )

    rules = rules or {}

    common_metrics = (
        baseline.aggregate_metrics.keys()
        & candidate.aggregate_metrics.keys()
    )

    metric_results: list[MetricComparison] = []

    for metric in sorted(common_metrics):
        rule = rules.get(
            metric,
            MetricRule(),
        )

        metric_results.append(
            _compare_metric(
                metric=metric,
                baseline=baseline.aggregate_metrics[
                    metric
                ],
                candidate=candidate.aggregate_metrics[
                    metric
                ],
                rule=rule,
            )
        )

    baseline_failed = _failed_case_ids(
        baseline
    )
    candidate_failed = _failed_case_ids(
        candidate
    )

    newly_failed = sorted(
        candidate_failed - baseline_failed
    )

    resolved = sorted(
        baseline_failed - candidate_failed
    )

    regression_passed = all(
        metric.passed
        for metric in metric_results
    )

    return ExperimentComparison(
        baseline_id=baseline.experiment_id,
        candidate_id=candidate.experiment_id,
        system=baseline.system,
        passed=(
            candidate.passed
            and regression_passed
        ),
        metrics=metric_results,
        newly_failed_cases=newly_failed,
        resolved_cases=resolved,
    )