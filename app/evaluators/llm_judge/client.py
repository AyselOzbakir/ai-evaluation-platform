"""Client contracts for generic LLM-as-a-Judge evaluation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol


class JudgeClientConfigurationError(RuntimeError):
    """Raised when an optional production judge client is not configured."""


@dataclass(frozen=True)
class JudgeResponse:
    score: float
    reason: str
    passed: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ValueError("JudgeResponse score must be numeric")
        if not 0 <= self.score <= 1:
            raise ValueError("JudgeResponse score must be between 0 and 1")
        if not isinstance(self.reason, str):
            raise ValueError("JudgeResponse reason must be a string")
        if self.passed is not None and not isinstance(self.passed, bool):
            raise ValueError("JudgeResponse passed must be a boolean or None")
        if not isinstance(self.metadata, dict):
            raise ValueError("JudgeResponse metadata must be a mapping")


class JudgeClient(Protocol):
    def judge(self, prompt: str) -> JudgeResponse: ...


class StaticJudgeClient:
    """Small deterministic client useful for local runs and tests."""

    def __init__(self, response: JudgeResponse) -> None:
        self.response = response
        self.prompts: list[str] = []

    def judge(self, prompt: str) -> JudgeResponse:
        self.prompts.append(prompt)
        return self.response


class OpenAIJudgeClient:
    """Optional lazy OpenAI-compatible client; no provider import at module load."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.environ.get("LLM_JUDGE_MODEL")
        self.api_key = api_key or os.environ.get("LLM_JUDGE_API_KEY")
        self.base_url = base_url or os.environ.get("LLM_JUDGE_BASE_URL")
        if not self.api_key:
            raise JudgeClientConfigurationError(
                "LLM judge API key is not configured; set LLM_JUDGE_API_KEY."
            )
        if not self.model:
            raise JudgeClientConfigurationError(
                "LLM judge model is not configured; set LLM_JUDGE_MODEL."
            )

    def judge(self, prompt: str) -> JudgeResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise JudgeClientConfigurationError(
                "The optional OpenAI judge client requires the 'openai' package."
            ) from exc

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)
        response = client.responses.create(
            model=self.model,
            input=prompt,
        )
        try:
            payload = json.loads(response.output_text)
        except (AttributeError, json.JSONDecodeError) as exc:
            raise RuntimeError("LLM judge returned a non-JSON response") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("LLM judge response must be a JSON object")
        return JudgeResponse(
            score=payload.get("score"),
            reason=payload.get("reason", ""),
            passed=payload.get("passed"),
            metadata=payload.get("metadata", {}),
        )