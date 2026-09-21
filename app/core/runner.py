"""The generic evaluation runner. Works with any SystemAdapter/Evaluator registered under app.core.registry."""

from datetime import UTC, datetime

from app.core.config import RunConfig
from app.core.datasets import load_dataset
from app.core.experiment import CaseResult, ExperimentResult
from app.core.hooks import NoOpObservabilityHook, ObservabilityHook
from app.core.models import EvaluationResult
from app.core.registry import Registry
from app.core.storage import save_experiment


def _make_experiment_id(system: str, label: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S%f")
    return f"{timestamp}_{system}_{label}"


def run_experiment(
    config: RunConfig,
    registry: Registry,
    experiment_id: str | None = None,
    label: str = "run",
    hook: ObservabilityHook | None = None,
    persist: bool = True,
) -> ExperimentResult:
    hook = hook or NoOpObservabilityHook()
    experiment_id = experiment_id or _make_experiment_id(config.system, label)
    started_at = datetime.now(UTC).isoformat()

    cases = load_dataset(config.dataset_path)
    adapter = registry.get_adapter(config.system)
    evaluators = [registry.get_evaluator(name) for name in config.evaluators]

    case_results: list[CaseResult] = []
    for case in cases:
        try:
            output = adapter.run(case)
        except Exception as exc:  # noqa: BLE001 - a broken adapter must not crash the experiment
            result = CaseResult(case_id=case.id, output=None, evaluations=[], error=str(exc))
            case_results.append(result)
            hook.on_case_evaluated(case, None, result)
            continue

        evaluations: list[EvaluationResult] = []
        for evaluator in evaluators:
            try:
                evaluations.append(evaluator.evaluate(case, output))
            except Exception as exc:  # noqa: BLE001 - one broken evaluator must not drop the case
                evaluations.append(
                    EvaluationResult(
                        evaluator=evaluator.name,
                        score=None,
                        passed=False,
                        reason=f"evaluator crashed: {exc}",
                    )
                )

        result = CaseResult(case_id=case.id, output=output, evaluations=evaluations, error=None)
        case_results.append(result)
        hook.on_case_evaluated(case, output, result)

    aggregate_metrics = _aggregate(case_results)
    passed = _passed(case_results, aggregate_metrics, config.thresholds)

    experiment = ExperimentResult(
        experiment_id=experiment_id,
        system=config.system,
        dataset_version=config.dataset_version,
        application_version=config.application_version,
        started_at=started_at,
        case_results=case_results,
        aggregate_metrics=aggregate_metrics,
        passed=passed,
    )

    if persist:
        save_experiment(experiment)
    hook.on_experiment_completed(experiment)
    return experiment


def _aggregate(case_results: list[CaseResult]) -> dict[str, float]:
    scores_by_evaluator: dict[str, list[float]] = {}
    passed_by_evaluator: dict[str, list[bool]] = {}

    for case_result in case_results:
        for evaluation in case_result.evaluations:
            scores_by_evaluator.setdefault(evaluation.evaluator, [])
            passed_by_evaluator.setdefault(evaluation.evaluator, [])
            if evaluation.score is not None:
                scores_by_evaluator[evaluation.evaluator].append(evaluation.score)
            passed_by_evaluator[evaluation.evaluator].append(evaluation.passed)

    metrics: dict[str, float] = {}
    for name, scores in scores_by_evaluator.items():
        if scores:
            metrics[f"{name}_avg_score"] = sum(scores) / len(scores)
    for name, flags in passed_by_evaluator.items():
        if flags:
            metrics[f"{name}_pass_rate"] = sum(flags) / len(flags)

    total_cases = len(case_results)
    error_count = sum(1 for case_result in case_results if case_result.error is not None)
    if total_cases:
        metrics["case_error_rate"] = error_count / total_cases
    return metrics


def _passed(
    case_results: list[CaseResult],
    aggregate_metrics: dict[str, float],
    thresholds: dict[str, float],
) -> bool:
    if any(case_result.error is not None for case_result in case_results):
        return False
    for evaluator_name, minimum in thresholds.items():
        avg_score = aggregate_metrics.get(f"{evaluator_name}_avg_score")
        if avg_score is not None and avg_score < minimum:
            return False
    return True
