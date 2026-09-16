"""Frozen shared contract. Field names and semantics must not change without agreement from all five people."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    id: str
    system: str
    input: dict[str, Any]
    expected_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemOutput(BaseModel):
    output: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    evaluator: str
    score: float | None = None
    passed: bool
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemAdapter(ABC):
    @abstractmethod
    def run(self, case: EvaluationCase) -> SystemOutput: ...


class Evaluator(ABC):
    name: str

    @abstractmethod
    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult: ...
