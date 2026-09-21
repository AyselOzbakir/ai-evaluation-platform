"""Fail-open Langfuse observability hook for evaluation runs."""

from __future__ import annotations

from typing import Any

from app.core.experiment import CaseResult, ExperimentResult
from app.core.models import EvaluationCase, SystemOutput
from app.integrations.langfuse.client import DisabledLangfuseClient
from app.integrations.langfuse.metadata import evaluation_metadata


class LangfuseObservabilityHook:
    def __init__(self, client: Any, experiment_context: dict[str, Any]) -> None:
        self.client = client
        self.experiment_context = experiment_context

    def on_case_evaluated(
        self,
        case: EvaluationCase,
        output: SystemOutput | None,
        result: CaseResult,
    ) -> None:
        if not getattr(self.client, "enabled", False):
            return
        try:
            case_metadata = evaluation_metadata(
                **self.experiment_context,
                case_id=case.id,
            )
            case_observation = self.client.start_observation(
                name=f"case:{case.id}",
                metadata=case_metadata,
                input_data={"case_id": case.id},
            )
            for evaluation in result.evaluations:
                evaluator_metadata = evaluation_metadata(
                    **case_metadata,
                    evaluator=evaluation.evaluator,
                )
                evaluator_observation = case_observation.start_observation(
                    name=f"evaluator:{evaluation.evaluator}",
                    metadata=evaluator_metadata,
                )
                if evaluation.score is not None:
                    evaluator_observation.score(
                        name=evaluation.evaluator,
                        value=float(evaluation.score),
                        data_type="NUMERIC",
                        comment=evaluation.reason,
                    )
                evaluator_observation.score(
                    name=f"{evaluation.evaluator}.passed",
                    value=1 if evaluation.passed else 0,
                    data_type="BOOLEAN",
                    comment=evaluation.reason,
                )
                evaluator_observation.end()
            case_observation.end()
        except Exception:
            return None

    def on_experiment_completed(self, experiment: ExperimentResult) -> None:
        try:
            self.client.flush()
        except Exception:
            return None


def disabled_hook(experiment_context: dict[str, Any]) -> LangfuseObservabilityHook:
    return LangfuseObservabilityHook(DisabledLangfuseClient(), experiment_context)