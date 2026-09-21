"""FastAPI routes for the evaluation platform. Reads/writes only through app.core."""

from fastapi import APIRouter, HTTPException

from app.core.config import RunConfig
from app.core.experiment import ExperimentResult
from app.core.registry import Registry, RegistryError, registry as default_registry
from app.core.storage import StorageError, list_experiments, load_experiment
from app.services.evaluation import run_configured_experiment
from app.services.human_evaluation import (
    HumanEvaluationResponse,
    HumanEvaluationSubmission,
    create_human_evaluation,
    list_human_evaluations,
)

router = APIRouter()


def get_registry() -> Registry:
    return default_registry


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/systems")
def systems() -> list[str]:
    return get_registry().list_systems()


@router.post("/evaluations/run", response_model=ExperimentResult)
def run_evaluation(config: RunConfig) -> ExperimentResult:
    try:
        return run_configured_experiment(config, get_registry())
    except RegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evaluations/{experiment_id}", response_model=ExperimentResult)
def get_evaluation(experiment_id: str) -> ExperimentResult:
    return _load_or_404(experiment_id)


@router.get("/experiments")
def list_all_experiments() -> list[str]:
    return list_experiments()


@router.get("/experiments/{experiment_id}", response_model=ExperimentResult)
def get_experiment(experiment_id: str) -> ExperimentResult:
    return _load_or_404(experiment_id)


@router.post(
    "/human-evaluations",
    response_model=HumanEvaluationResponse,
    status_code=201,
)
def submit_human_evaluation(
    submission: HumanEvaluationSubmission,
) -> HumanEvaluationResponse:
    try:
        return create_human_evaluation(submission)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/human-evaluations/{experiment_id}",
    response_model=list[HumanEvaluationResponse],
)
def get_human_evaluations(experiment_id: str) -> list[HumanEvaluationResponse]:
    try:
        return list_human_evaluations(experiment_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _load_or_404(experiment_id: str) -> ExperimentResult:
    try:
        return load_experiment(experiment_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
