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