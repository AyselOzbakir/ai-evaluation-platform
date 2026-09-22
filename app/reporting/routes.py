import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.storage import StorageError, load_experiment
from app.experiments.comparison import (
    ExperimentComparison,
    compare_experiments,
)
from app.experiments.rules import load_metric_rules

router = APIRouter()

DASHBOARD_FILE = (
    Path(__file__).resolve().parents[1]
    / "static"
    / "dashboard.html"
)
REGRESSION_RULES_FILE = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "regression_rules.yaml"
)
EXPERIMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
OBSERVABILITY_FIELDS = {
    "experiment_id",
    "enabled",
    "langfuse_trace_id",
    "langfuse_trace_url",
    "langfuse_observation_id",
    "langfuse_dataset_name",
    "langfuse_dataset_run_id",
    "langfuse_dataset_run_url",
}


@router.get("/dashboard", response_class=FileResponse)
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_FILE)


@router.get("/dashboard/observability/{experiment_id}")
def experiment_observability(experiment_id: str) -> dict[str, object]:
    if not EXPERIMENT_ID_PATTERN.fullmatch(experiment_id):
        raise HTTPException(status_code=400, detail="Invalid experiment ID.")

    artifact_dir = Path(
        os.environ.get("EXPERIMENT_ARTIFACT_DIR", "artifacts/experiments")
    )
    sidecar_path = artifact_dir.parent / "observability" / f"{experiment_id}.json"
    response: dict[str, object] = {
        "experiment_id": experiment_id,
        "enabled": False,
    }
    if not sidecar_path.is_file():
        return response

    try:
        raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return response
    if not isinstance(raw, dict):
        return response

    for field in OBSERVABILITY_FIELDS:
        if field in raw and field != "experiment_id":
            response[field] = raw[field]
    return response


@router.get(
    "/dashboard/compare",
    response_model=ExperimentComparison,
)
def compare_dashboard_experiments(
    baseline_id: str,
    candidate_id: str,
) -> ExperimentComparison:
    try:
        baseline = load_experiment(baseline_id)
        candidate = load_experiment(candidate_id)
    except StorageError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    try:
        rules = load_metric_rules(REGRESSION_RULES_FILE)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    try:
        return compare_experiments(
            baseline,
            candidate,
            rules,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
