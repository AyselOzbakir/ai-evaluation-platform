import pytest

from app.evaluators.llm_judge.client import (
    JudgeClientConfigurationError,
    JudgeResponse,
    OpenAIJudgeClient,
    StaticJudgeClient,
)


def test_static_client_returns_response_and_records_prompt():
    response = JudgeResponse(score=0.8, reason="Good match.")
    client = StaticJudgeClient(response)

    assert client.judge("prompt") == response
    assert client.prompts == ["prompt"]


def test_judge_response_rejects_invalid_score():
    with pytest.raises(ValueError, match="between 0 and 1"):
        JudgeResponse(score=2, reason="invalid")


def test_optional_production_client_requires_credentials(monkeypatch):
    monkeypatch.delenv("LLM_JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_JUDGE_MODEL", raising=False)

    with pytest.raises(JudgeClientConfigurationError, match="API key"):
        OpenAIJudgeClient()


def test_optional_production_client_requires_model(monkeypatch):
    monkeypatch.setenv("LLM_JUDGE_API_KEY", "synthetic-key")
    monkeypatch.delenv("LLM_JUDGE_MODEL", raising=False)

    with pytest.raises(JudgeClientConfigurationError, match="model"):
        OpenAIJudgeClient()