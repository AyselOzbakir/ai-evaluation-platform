"""Runner wrapper that adds optional Langfuse tracing without changing core."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import RunConfig
from app.core.experiment import ExperimentResult
from app.core.registry import Registry
from app.core.runner import _make_experiment_id, run_experiment
from app.integrations.langfuse.client import create_client, safe_trace_url
from app.integrations.langfuse.hook import LangfuseObservabilityHook
from app.integrations.langfuse.metadata import evaluation_metadata, observability_sidecar


def run_experiment_with_langfuse(
    config: RunConfig,
    registry: Registry,
    experiment_id: str | None = None,
    label: str = "run",
    persist: bool = True,
    client: Any | None = None,
) -> ExperimentResult:
    langfuse = client or create_client()
    resolved_id = experiment_id or _make_experiment_id(config.system, label)
    context = evaluation_metadata(
        experiment_id=resolved_id,
        system=config.system,
        dataset_version=config.dataset_version,
        application_version=config.application_version,
    )

    root = langfuse
    try:
        if getattr(langfuse, "enabled", False):
            root = langfuse.start_trace(
                name=f"experiment:{resolved_id}",
                metadata=context,
                input_data={"experiment_id": resolved_id},
            )
        hook = LangfuseObservabilityHook(root, context)
        experiment = run_experiment(
            config,
            registry,
            experiment_id=resolved_id,
            label=label,
            hook=hook,
            persist=persist,
        )
    except Exception:
        try:
            root.end()
        except Exception:
            pass
        raise

    try:
        root.update(output={"passed": experiment.passed, "experiment_id": experiment.experiment_id})
        root.end()
    except Exception:
        pass
    _write_sidecar(experiment, langfuse)
    return experiment


def _write_sidecar(experiment: ExperimentResult, client: Any) -> None:
    artifact_dir = Path(os.environ.get("EXPERIMENT_ARTIFACT_DIR", "artifacts/experiments"))
    sidecar_path = artifact_dir.parent / "observability" / f"{experiment.experiment_id}.json"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    trace_id = getattr(client, "trace_id", None)
    sidecar_path.write_text(
        json.dumps(
            observability_sidecar(
                experiment.experiment_id,
                bool(getattr(client, "enabled", False)),
                trace_id=trace_id,
                trace_url_value=safe_trace_url(client),
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )