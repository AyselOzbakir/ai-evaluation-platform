"""Optional ATA token/cost measurement evaluators."""

from __future__ import annotations

from app.core.models import EvaluationCase, EvaluationResult, Evaluator, SystemOutput


class _UsageEvaluator(Evaluator):
    field: str
    label: str

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        value = output.metadata.get(self.field)
        if value is None:
            return EvaluationResult(
                evaluator=self.name,
                score=None,
                passed=True,
                reason=f"{self.label} unavailable from ATA backend.",
                metadata={
                    "available": False,
                    "metric": self.field,
                    "aggregate_name": self.field,
                },
            )
        return EvaluationResult(
            evaluator=self.name,
            score=float(value),
            passed=True,
            reason=f"Measured {self.label}: {value}.",
            metadata={
                "available": True,
                "metric": self.field,
                "aggregate_name": self.field,
            },
        )


class InputTokensEvaluator(_UsageEvaluator):
    name = "input_tokens"
    field = "input_tokens"
    label = "input tokens"


class OutputTokensEvaluator(_UsageEvaluator):
    name = "output_tokens"
    field = "output_tokens"
    label = "output tokens"


class TotalTokensEvaluator(_UsageEvaluator):
    name = "total_tokens"
    field = "total_tokens"
    label = "total tokens"


class CostUsdEvaluator(_UsageEvaluator):
    name = "cost_usd"
    field = "cost_usd"
    label = "cost in USD"


def usage_evaluators() -> list[Evaluator]:
    return [
        InputTokensEvaluator(),
        OutputTokensEvaluator(),
        TotalTokensEvaluator(),
        CostUsdEvaluator(),
    ]