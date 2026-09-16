"""Fake adapter/evaluator so core tests never need a real system or an LLM."""

from app.core.models import Evaluator, EvaluationCase, EvaluationResult, SystemAdapter, SystemOutput


class FakeAdapter(SystemAdapter):
    """Echoes case.input back as output.output; raises for cases whose id contains 'boom'."""

    def run(self, case: EvaluationCase) -> SystemOutput:
        if "boom" in case.id:
            raise RuntimeError(f"fake adapter failure for case {case.id}")
        return SystemOutput(output=dict(case.input), metadata={"system": case.system})


class FakeEvaluator(Evaluator):
    """Passes when output.output equals case.expected_output; score 1.0/0.0 accordingly."""

    name = "fake_exact_match"

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        matched = output.output == case.expected_output
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if matched else 0.0,
            passed=matched,
            reason="exact match" if matched else "output does not match expected_output",
        )


class CrashingEvaluator(Evaluator):
    name = "crashing_evaluator"

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        raise RuntimeError("evaluator exploded")
