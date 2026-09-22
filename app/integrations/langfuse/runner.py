"""Runner wrapper that adds optional Langfuse tracing without changing core."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import RunConfig
from app.core.config import RunConfig
from app.core.experiment import CaseResult, ExperimentResult
from app.core.models import EvaluationCase, EvaluationResult, SystemOutput
from app.core.registry import Registry
from app.core.runner import _aggregate, _make_experiment_id, _passed, run_experiment
from app.integrations.langfuse.client import create_client, safe_trace_url
from app.integrations.langfuse.datasets import dataset_name_for_system
from app.integrations.langfuse.hook import LangfuseObservabilityHook
from app.integrations.langfuse.metadata import evaluation_metadata, observability_sidecar


def run_experiment_with_langfuse(
    config: RunConfig,
    registry: Registry,
    experiment_id: str | None = None,
    label: str = "run",
    persist: bool = True,
    client: Any | None = None,
) -> ExperimentResult:
    langfuse = client or create_client()
    resolved_id = experiment_id or _make_experiment_id(config.system, label)
    context = evaluation_metadata(
        experiment_id=resolved_id,
        system=config.system,
        dataset_version=config.dataset_version,
        application_version=config.application_version,
    )
    dataset_name = None
    if os.environ.get("LANGFUSE_DATASET_PREFIX"):
        dataset_name = dataset_name_for_system(config.system)
        context["langfuse_dataset_name"] = dataset_name
        context["langfuse_dataset_version"] = config.dataset_version

    root = langfuse
    try:
        if dataset_name and getattr(langfuse, "enabled", False):
            try:
                experiment = _run_hosted_dataset_experiment(
                    config=config,
                    registry=registry,
                    client=langfuse,
                    dataset_name=dataset_name,
                    experiment_id=resolved_id,
                    persist=persist,
                )
                _write_sidecar(experiment, langfuse, dataset_run=experiment.metadata.get("langfuse_dataset_run"))
                return experiment
            except Exception:
                # Missing dataset, SDK incompatibility, or network failure falls back locally.
                pass
        if getattr(langfuse, "enabled", False):
            root = langfuse.start_trace(
                name=f"experiment:{resolved_id}",
                metadata=context,
                input_data={"experiment_id": resolved_id},
            )
        hook = LangfuseObservabilityHook(root, context)
        experiment = run_experiment(
            config,
            registry,
            experiment_id=resolved_id,
            label=label,
            hook=hook,
            persist=persist,
        )
    except Exception:
        try:
            root.end()
        except Exception:
            pass
        raise

    try:
        root.update(output={"passed": experiment.passed, "experiment_id": experiment.experiment_id})
        root.end()
    except Exception:
        pass
    _write_sidecar(experiment, langfuse)
    return experiment


def _run_hosted_dataset_experiment(
    *,
    config: RunConfig,
    registry: Registry,
    client: Any,
    dataset_name: str,
    experiment_id: str,
    persist: bool,
) -> ExperimentResult:
    dataset = client.get_dataset(dataset_name)
    case_results: dict[str, CaseResult] = {}
    started_at = datetime.now(UTC).isoformat()

    def task(*, item: Any, **kwargs: Any) -> dict[str, Any]:
        case = _case_from_dataset_item(item, config.system)
        try:
            output = registry.get_adapter(config.system).run(case)
        except Exception as exc:  # noqa: BLE001
            result = CaseResult(case_id=case.id, output=None, evaluations=[], error=str(exc))
            case_results[case.id] = result
            return {"error": str(exc), "case_id": case.id}

        evaluations: list[EvaluationResult] = []
        for evaluator_name in config.evaluators:
            evaluator = registry.get_evaluator(evaluator_name)
            try:
                evaluations.append(evaluator.evaluate(case, output))
            except Exception as exc:  # noqa: BLE001
                evaluations.append(
                    EvaluationResult(
                        evaluator=evaluator.name,
                        score=None,
                        passed=False,
                        reason=f"evaluator crashed: {exc}",
                    )
                )
        result = CaseResult(
            case_id=case.id,
            output=output,
            evaluations=evaluations,
            error=None,
        )
        case_results[case.id] = result
        return {
            "case_id": case.id,
            "output": output.model_dump(mode="json"),
            "evaluations": [evaluation.model_dump(mode="json") for evaluation in evaluations],
        }

    def evaluator_bridge(*, input: Any, output: Any, metadata: Any, **kwargs: Any) -> dict[str, Any]:
        name = metadata.get("evaluator") if isinstance(metadata, dict) else None
        evaluations = output.get("evaluations", []) if isinstance(output, dict) else []
        for evaluation in evaluations:
            if name is None or evaluation.get("evaluator") == name:
                return {
                    "name": evaluation.get("evaluator", name or "evaluation"),
                    "value": evaluation.get("score") or 0.0,
                    "comment": evaluation.get("reason", ""),
                }
        return {"name": name or "evaluation", "value": 0.0, "comment": "No result"}

    evaluator_functions = [
        _named_langfuse_evaluator(name, evaluator_bridge)
        for name in config.evaluators
    ]
    sdk_result = client.run_dataset_experiment(
        dataset,
        name=f"{config.system} evaluation",
        run_name=experiment_id,
        description="AI Evaluation Platform experiment",
        task=task,
        evaluators=evaluator_functions,
        metadata={
            "experiment_id": experiment_id,
            "system": config.system,
            "dataset_version": config.dataset_version,
            "application_version": config.application_version,
            "evaluators": ",".join(config.evaluators),
            "timestamp": started_at,
        },
    )
    ordered_results = list(case_results.values())
    aggregate_metrics = _aggregate(ordered_results)
    passed = _passed(ordered_results, aggregate_metrics, config.thresholds)
    dataset_run_id = _result_value(sdk_result, "dataset_run_id")
    dataset_run_url = _result_value(sdk_result, "dataset_run_url")
    metadata = {
        "langfuse_dataset_name": dataset_name,
        "langfuse_dataset_run_id": dataset_run_id,
        "langfuse_dataset_run_url": dataset_run_url,
    }
    experiment = ExperimentResult(
        experiment_id=experiment_id,
        system=config.system,
        dataset_version=config.dataset_version,
        application_version=config.application_version,
        started_at=started_at,
        case_results=ordered_results,
        aggregate_metrics=aggregate_metrics,
        passed=passed,
        metadata=metadata,
    )
    if persist:
        from app.core.storage import save_experiment

        save_experiment(experiment)
    return experiment


def _case_from_dataset_item(item: Any, system: str) -> EvaluationCase:
    metadata = dict(getattr(item, "metadata", None) or item.get("metadata", {}) or {})
    item_input = getattr(item, "input", None)
    expected = getattr(item, "expected_output", None)
    if isinstance(item, dict):
        item_input = item.get("input", item_input)
        expected = item.get("expected_output", expected)
    case_id = getattr(item, "id", None) or metadata.get("case_id")
    if isinstance(item, dict):
        case_id = item.get("id", case_id)
    return EvaluationCase(
        id=case_id,
        system=system,
        input=item_input or {},
        expected_output=expected or {},
        metadata=metadata,
    )


def _named_langfuse_evaluator(name: str, bridge: Any) -> Any:
    def evaluate(*, input: Any, output: Any, expected_output: Any = None, metadata: Any = None, **kwargs: Any) -> Any:
        return bridge(input=input, output=output, expected_output=expected_output, metadata={"evaluator": name}, **kwargs)

    evaluate.__name__ = name
    return evaluate


def _result_value(result: Any, name: str) -> Any:
    if isinstance(result, dict):
        return result.get(name)
    return getattr(result, name, None)


def _write_sidecar(
    experiment: ExperimentResult,
    client: Any,
    dataset_run: Any = None,
) -> None:
    artifact_dir = Path(os.environ.get("EXPERIMENT_ARTIFACT_DIR", "artifacts/experiments"))
    sidecar_path = artifact_dir.parent / "observability" / f"{experiment.experiment_id}.json"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    trace_id = getattr(client, "trace_id", None)
    sidecar_path.write_text(
        json.dumps(
            observability_sidecar(
                experiment.experiment_id,
                bool(getattr(client, "enabled", False)),
                trace_id=trace_id,
                trace_url_value=safe_trace_url(client),
                dataset_name=experiment.metadata.get("langfuse_dataset_name"),
                dataset_run_id=experiment.metadata.get("langfuse_dataset_run_id"),
                dataset_run_url=experiment.metadata.get("langfuse_dataset_run_url"),
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )