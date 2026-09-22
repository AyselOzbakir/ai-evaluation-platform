"""Stable metadata and trace URL helpers for Langfuse integration."""

from __future__ import annotations

from typing import Any

METADATA_KEYS = (
    "experiment_id",
    "system",
    "dataset_version",
    "application_version",
    "case_id",
    "evaluator",
)


def evaluation_metadata(**values: Any) -> dict[str, Any]:
    return {key: values[key] for key in METADATA_KEYS if values.get(key) is not None}


def trace_url(
    base_url: str | None,
    project_id: str | None,
    trace_id: str | None,
) -> str | None:
    if not base_url or not project_id or not trace_id:
        return None
    return f"{base_url.rstrip('/')}/project/{project_id}/traces/{trace_id}"


def observability_sidecar(
    experiment_id: str,
    enabled: bool,
    trace_id: str | None = None,
    trace_url_value: str | None = None,
    dataset_name: str | None = None,
    dataset_run_id: str | None = None,
    dataset_run_url: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "experiment_id": experiment_id,
        "enabled": enabled,
    }
    if trace_id:
        data["langfuse_trace_id"] = trace_id
    if trace_url_value:
        data["langfuse_trace_url"] = trace_url_value
    if dataset_name:
        data["langfuse_dataset_name"] = dataset_name
    if dataset_run_id:
        data["langfuse_dataset_run_id"] = dataset_run_id
    if dataset_run_url:
        data["langfuse_dataset_run_url"] = dataset_run_url
    return data