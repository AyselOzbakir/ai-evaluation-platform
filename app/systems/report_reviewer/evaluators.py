"""Deterministic evaluators for normalized report-reviewer outputs."""

from __future__ import annotations

from app.core.models import EvaluationCase, EvaluationResult, Evaluator, SystemOutput

ALLOWED_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REJECTED"}
ALLOWED_CHECK_STATUSES = {"PASS", "WARNING", "FAIL"}


class ReportDecisionEvaluator(Evaluator):
    name = "report_decision"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        expected = case.expected_output.get("status")
        actual = output.output.get("status")
        passed = actual == expected
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=f"Expected status {expected!r}; received {actual!r}.",
            metadata={"expected": expected, "actual": actual},
        )


class ReportFindingEvaluator(Evaluator):
    name = "report_findings"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        expected = case.expected_output.get("findings", {})
        checks = output.output.get("checks", [])
        if not isinstance(expected, dict):
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="Expected findings must be a title-to-status mapping.",
            )

        actual = {
            check.get("title"): check.get("status")
            for check in checks
            if isinstance(check, dict) and isinstance(check.get("title"), str)
        }
        matched = [
            title
            for title, status in expected.items()
            if actual.get(title) == status
        ]
        missing = [title for title in expected if title not in actual]
        mismatched = [
            title
            for title, status in expected.items()
            if title in actual and actual[title] != status
        ]
        score = len(matched) / len(expected) if expected else float(not actual)
        passed = score == 1.0 and not missing and not mismatched
        return EvaluationResult(
            evaluator=self.name,
            score=score,
            passed=passed,
            reason=f"Matched {len(matched)}/{len(expected)} expected findings.",
            metadata={
                "matched": matched,
                "missing": missing,
                "mismatched": mismatched,
            },
        )


class ReportSchemaEvaluator(Evaluator):
    name = "report_schema"

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        problems: list[str] = []
        result = output.output

        if result.get("status") not in ALLOWED_STATUSES:
            problems.append("status is invalid")

        score = result.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            problems.append("score must be numeric")
        elif not 0 <= score <= 100:
            problems.append("score must be between 0 and 100")

        if not isinstance(result.get("summary"), str):
            problems.append("summary must be a string")

        checks = result.get("checks")
        if not isinstance(checks, list):
            problems.append("checks must be a list")
        else:
            for index, check in enumerate(checks):
                if not isinstance(check, dict):
                    problems.append(f"check {index} must be an object")
                    continue
                if not isinstance(check.get("title"), str):
                    problems.append(f"check {index} title must be a string")
                if check.get("status") not in ALLOWED_CHECK_STATUSES:
                    problems.append(f"check {index} status is invalid")
                if not isinstance(check.get("message"), str):
                    problems.append(f"check {index} message must be a string")
                if not isinstance(check.get("evidence"), str):
                    problems.append(f"check {index} evidence must be a string")

        passed = not problems
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason="Report output schema is valid." if passed else "; ".join(problems),
            metadata={"problems": problems},
        )