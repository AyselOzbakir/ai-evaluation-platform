"""Optional observability hook. Person 4 implements this against Langfuse; the core never imports Langfuse."""

from typing import Protocol

from app.core.experiment import CaseResult, ExperimentResult
from app.core.models import EvaluationCase, SystemOutput


class ObservabilityHook(Protocol):
    def on_case_evaluated(
        self, case: EvaluationCase, output: SystemOutput | None, result: CaseResult
    ) -> None: ...

    def on_experiment_completed(self, experiment: ExperimentResult) -> None: ...


class NoOpObservabilityHook:
    def on_case_evaluated(
        self, case: EvaluationCase, output: SystemOutput | None, result: CaseResult
    ) -> None:
        pass

    def on_experiment_completed(self, experiment: ExperimentResult) -> None:
        pass
