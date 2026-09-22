import json

from app.core.config import RunConfig
from app.core.registry import Registry
from app.core.runner import run_experiment
from app.core.models import EvaluationCase, EvaluationResult, SystemAdapter, SystemOutput, Evaluator


class UsageAdapter(SystemAdapter):
    def run(self, case: EvaluationCase) -> SystemOutput:
        return SystemOutput(output={}, metadata={"input_tokens": 10, "cost_usd": 0.25})


class UsageEvaluator(Evaluator):
    name = "input_tokens"

    def evaluate(self, case, output):
        return EvaluationResult(
            evaluator=self.name,
            score=output.metadata["input_tokens"],
            passed=True,
            metadata={"aggregate_name": "input_tokens"},
        )


def test_metadata_driven_usage_aggregates(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps([{"id": "c1", "system": "usage", "input": {}}]))
    registry = Registry()
    registry.register_adapter("usage", UsageAdapter())
    registry.register_evaluator("input_tokens", UsageEvaluator())

    result = run_experiment(
        RunConfig(system="usage", dataset_version="v1", dataset_path=str(dataset), evaluators=["input_tokens"]),
        registry,
        persist=False,
    )

    assert result.aggregate_metrics["input_tokens_avg"] == 10
    assert result.aggregate_metrics["input_tokens_sum"] == 10