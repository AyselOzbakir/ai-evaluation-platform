import json

from app.core.models import EvaluationCase, SystemOutput
from app.systems.ata_rag.adapter import ATARagAdapter
from app.systems.ata_rag.usage import normalize_usage
from app.systems.ata_rag.usage_evaluators import (
    CostUsdEvaluator,
    InputTokensEvaluator,
    TotalTokensEvaluator,
)


def test_prompt_completion_usage_is_normalized():
    usage = normalize_usage(
        {
            "usage": {"prompt_tokens": 10, "completion_tokens": 7},
            "model": "synthetic-model",
        }
    )

    assert usage == {
        "input_tokens": 10.0,
        "output_tokens": 7.0,
        "total_tokens": 17.0,
        "cost_usd": None,
        "model_name": "synthetic-model",
    }


def test_input_output_usage_format_is_supported():
    usage = normalize_usage(
        {"input_tokens": 4, "output_tokens": 6, "total_tokens": 10}
    )

    assert usage["total_tokens"] == 10.0
    assert usage["cost_usd"] is None


def test_backend_cost_takes_precedence():
    usage = normalize_usage(
        {
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.25},
            "model": "unknown-model",
        },
        pricing_path="does-not-exist.yaml",
    )

    assert usage["cost_usd"] == 0.25


def test_pricing_config_calculates_cost(tmp_path):
    pricing = tmp_path / "pricing.yaml"
    pricing.write_text(
        "models:\n  synthetic-model:\n    input_usd_per_1m_tokens: 2\n    output_usd_per_1m_tokens: 4\n",
        encoding="utf-8",
    )

    usage = normalize_usage(
        {"input_tokens": 1000, "output_tokens": 500, "model": "synthetic-model"},
        pricing,
    )

    assert usage["cost_usd"] == 0.004


def test_unknown_model_does_not_fabricate_cost():
    usage = normalize_usage(
        {"input_tokens": 100, "output_tokens": 100, "model": "unknown"},
        "/tmp/does-not-exist.yaml",
    )
    assert usage["cost_usd"] is None


def test_adapter_preserves_unavailable_usage():
    raw = {"answer": "answer", "sources": []}
    output = ATARagAdapter.normalize_response(raw)

    assert output.metadata["input_tokens"] is None
    assert output.metadata["output_tokens"] is None
    assert output.metadata["total_tokens"] is None
    assert output.metadata["cost_usd"] is None


def test_usage_evaluators_are_neutral_when_unavailable():
    case = EvaluationCase(id="ata-rag-001", system="ata-rag", input={})
    output = SystemOutput(output={}, metadata={})

    result = InputTokensEvaluator().evaluate(case, output)

    assert result.score is None
    assert result.passed is True
    assert result.metadata["available"] is False


def test_usage_evaluators_return_numeric_values():
    case = EvaluationCase(id="ata-rag-001", system="ata-rag", input={})
    output = SystemOutput(
        output={},
        metadata={"total_tokens": 20, "cost_usd": 0.03},
    )

    assert TotalTokensEvaluator().evaluate(case, output).score == 20
    assert CostUsdEvaluator().evaluate(case, output).score == 0.03