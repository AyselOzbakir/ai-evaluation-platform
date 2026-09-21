"""Reusable generic LLM-as-a-Judge evaluator."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.core.models import EvaluationCase, EvaluationResult, Evaluator, SystemOutput
from app.evaluators.llm_judge.client import JudgeClient
from app.evaluators.llm_judge.rubric import Rubric


class LLMJudgeEvaluator(Evaluator):
    def __init__(
        self,
        rubric: Rubric,
        judge_client: JudgeClient,
        model_name: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.rubric = rubric
        self.judge_client = judge_client
        self.model_name = model_name
        self.provider = provider
        self.name = rubric.name

    def evaluate(
        self,
        case: EvaluationCase,
        output: SystemOutput,
    ) -> EvaluationResult:
        prompt = build_prompt(self.rubric, case, output)
        response = self.judge_client.judge(prompt)
        score = response.score
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("LLM judge score must be numeric")
        if not 0 <= score <= 1:
            raise ValueError("LLM judge score must be between 0 and 1")

        passed = (
            response.passed
            if response.passed is not None
            else score >= self.rubric.pass_threshold
        )
        return EvaluationResult(
            evaluator=self.rubric.name,
            score=float(score),
            passed=passed,
            reason=response.reason,
            metadata={
                "rubric": self.rubric.name,
                "prompt_version": self.rubric.prompt_version,
                "model": self.model_name,
                "provider": self.provider,
                "pass_threshold": self.rubric.pass_threshold,
            },
        )


def build_prompt(
    rubric: Rubric,
    case: EvaluationCase,
    output: SystemOutput,
) -> str:
    selected = {
        "input": _select_fields(case.input, rubric.fields.get("input", [])),
        "expected": _select_fields(
            case.expected_output,
            rubric.fields.get("expected", []),
        ),
        "actual": _select_fields(output.output, rubric.fields.get("actual", [])),
        "context": _select_fields(
            output.metadata,
            rubric.fields.get("context", []),
        ),
    }
    sections = [
        f"Rubric: {rubric.name}",
        f"Prompt version: {rubric.prompt_version}",
        "Criteria:",
        rubric.criteria,
        "Selected input:",
        json.dumps(selected["input"], ensure_ascii=False, separators=(",", ":")),
        "Selected expected output:",
        json.dumps(selected["expected"], ensure_ascii=False, separators=(",", ":")),
        "Selected actual output:",
        json.dumps(selected["actual"], ensure_ascii=False, separators=(",", ":")),
        "Selected context:",
        json.dumps(selected["context"], ensure_ascii=False, separators=(",", ":")),
        "Return a JSON object with score, reason, and optional passed.",
    ]
    return "\n".join(sections)


def _select_fields(source: Mapping[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: source.get(field) for field in fields}