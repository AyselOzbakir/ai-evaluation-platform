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


@router.get("/dashboard", response_class=FileResponse)
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_FILE)


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
