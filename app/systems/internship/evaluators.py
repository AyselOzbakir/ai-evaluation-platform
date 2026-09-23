"""Deterministic evaluators for Internship Coordinator outputs."""

from __future__ import annotations

from app.core.models import EvaluationCase, EvaluationResult, Evaluator, SystemOutput

ALLOWED_RECOMMENDATIONS = {
    "APPROVE",
    "REQUEST CLARIFICATION",
    "REJECT",
}


class CoordinatorDecisionEvaluator(Evaluator):
    name = "coordinator_decision"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        expected = case.expected_output.get("recommendation")
        actual = output.output.get("recommendation")
        passed = actual == expected
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=f"Expected recommendation {expected!r}; received {actual!r}.",
            metadata={"expected": expected, "actual": actual},
        )


class CoordinatorSchemaEvaluator(Evaluator):
    name = "coordinator_schema"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        problems: list[str] = []
        result = output.output
        if result.get("system") != "internship-coordinator":
            problems.append("system is invalid")
        if result.get("recommendation") not in ALLOWED_RECOMMENDATIONS:
            problems.append("recommendation is invalid")
        if result.get("external_decision") != "PENDING":
            problems.append("external_decision must be PENDING")
        if not isinstance(result.get("notes"), str) or not result["notes"].strip():
            problems.append("notes must be a non-empty string")
        if not isinstance(result.get("case_id"), str) or not result["case_id"].strip():
            problems.append("case_id must be a non-empty string")

        passed = not problems
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason="Coordinator output schema is valid." if passed else "; ".join(problems),
            metadata={"problems": problems},
        )


class CoordinatorLatencyThreshold(Evaluator):
    """Passes when the coordinator's reported latency is within ``max_ms``."""

    name = "coordinator_latency_threshold"

    def __init__(self, max_ms: int = 10_000) -> None:
        self.max_ms = max_ms

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        latency = output.metadata.get("latency_ms")
        if latency is None:
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="No latency_ms in output metadata.",
            )
        passed = latency <= self.max_ms
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=f"Latency {latency} ms vs limit {self.max_ms} ms.",
            metadata={"latency_ms": latency, "max_ms": self.max_ms},
        )


class CoordinatorNotesQualityEvaluator(Evaluator):
    """Deterministic floor for explanation quality: non-trivial, non-empty notes.

    This is a cheap proxy only (length + whitespace check), not a substitute for
    the LLM-judge ``explanation_quality`` rubric in configs/internship/rubrics.yaml,
    which actually judges whether the explanation is well-supported.
    """

    name = "coordinator_notes_quality"

    def __init__(self, min_length: int = 20) -> None:
        self.min_length = min_length

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        notes = output.output.get("notes", "")
        length = len(notes.strip()) if isinstance(notes, str) else 0
        passed = length >= self.min_length
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=(
                f"Notes are {length} characters long; minimum is {self.min_length}."
                if passed
                else f"Notes are too short ({length} chars) to explain a decision; "
                f"minimum is {self.min_length}."
            ),
            metadata={"notes_length": length, "min_length": self.min_length},
        )


class CoordinatorEvidenceEvaluator(Evaluator):
    name = "coordinator_evidence"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        expected = case.expected_output.get("evidence_markers")
        if not expected:
            return EvaluationResult(
                evaluator=self.name,
                score=None,
                passed=True,
                reason="No evidence markers configured; skipped.",
                metadata={"skipped": True},
            )
        if not isinstance(expected, list) or not all(
            isinstance(marker, str) for marker in expected
        ):
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="Expected evidence_markers must be a list of strings.",
            )

        notes = output.output.get("notes", "")
        matched = [marker for marker in expected if marker in notes]
        score = len(matched) / len(expected)
        return EvaluationResult(
            evaluator=self.name,
            score=score,
            passed=score == 1.0,
            reason=f"Matched {len(matched)}/{len(expected)} expected evidence markers.",
            metadata={"matched": matched, "missing": [m for m in expected if m not in matched]},
        )