"""ATA usage and cost normalization with explicit pricing only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def normalize_usage(
    raw: dict[str, Any],
    pricing_path: str | Path | None = None,
) -> dict[str, Any]:
    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}

    input_tokens = _first_number(
        usage.get("input_tokens"),
        usage.get("prompt_tokens"),
        raw.get("input_tokens"),
        raw.get("prompt_tokens"),
    )
    output_tokens = _first_number(
        usage.get("output_tokens"),
        usage.get("completion_tokens"),
        raw.get("output_tokens"),
        raw.get("completion_tokens"),
    )
    total_tokens = _first_number(
        usage.get("total_tokens"),
        raw.get("total_tokens"),
    )
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    model_name = raw.get("model_name") or raw.get("model") or usage.get("model_name") or usage.get("model")
    backend_cost = _first_number(
        usage.get("cost_usd"),
        usage.get("cost"),
        raw.get("cost_usd"),
        raw.get("cost"),
    )
    cost_usd = backend_cost
    if cost_usd is None:
        cost_usd = calculate_cost(input_tokens, output_tokens, model_name, pricing_path)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "model_name": model_name,
    }


def calculate_cost(
    input_tokens: float | None,
    output_tokens: float | None,
    model_name: str | None,
    pricing_path: str | Path | None = None,
) -> float | None:
    if input_tokens is None or output_tokens is None or not model_name or not pricing_path:
        return None
    path = Path(pricing_path)
    if not path.is_file():
        return None
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pricing = config.get("models", {}).get(model_name)
    if not isinstance(pricing, dict):
        return None
    input_rate = pricing.get("input_usd_per_1m_tokens")
    output_rate = pricing.get("output_usd_per_1m_tokens")
    if not isinstance(input_rate, (int, float)) or not isinstance(output_rate, (int, float)):
        return None
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


def _first_number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None