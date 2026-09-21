import json

from fastapi.testclient import TestClient

from app.bootstrap import register_default_integrations
from app.core.registry import Registry, registry
from app.core.storage import list_experiments
from app.main import app


def test_bootstrap_registers_expected_systems_and_is_idempotent():
    local_registry = Registry()

    register_default_integrations(local_registry)
    first_systems = local_registry.list_systems()
    first_evaluators = local_registry.list_evaluators()
    register_default_integrations(local_registry)

    assert first_systems == [
        "ata-rag",
        "internship-coordinator",
        "pdf-signer",
        "report-reviewer",
    ]
    assert local_registry.list_systems() == first_systems
    assert local_registry.list_evaluators() == first_evaluators


def test_bootstrap_requires_no_external_environment(monkeypatch):
    for name in (
        "ATA_RAG_BASE_URL",
        "INTERNSHIP_COORDINATOR_PATH",
        "REPORT_REVIEWER_PATH",
        "PDF_SIGNER_BACKEND_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    local_registry = Registry()
    register_default_integrations(local_registry)

    assert len(local_registry.list_systems()) == 4


def test_api_lists_registered_systems():
    response = TestClient(app).get("/systems")

    assert response.status_code == 200
    assert set(response.json()) >= {
        "ata-rag",
        "internship-coordinator",
        "report-reviewer",
        "pdf-signer",
    }


def test_api_run_reaches_application_service(monkeypatch):
    from app.core.experiment import ExperimentResult

    expected = ExperimentResult(
        experiment_id="api-integration",
        system="ata-rag",
        dataset_version="v1",
        application_version="test",
        started_at="2026-09-22T00:00:00Z",
        passed=True,
    )
    calls = []

    def fake_service(config, configured_registry):
        calls.append((config, configured_registry))
        return expected

    monkeypatch.setattr("app.api.routes.run_configured_experiment", fake_service)
    response = TestClient(app).post(
        "/evaluations/run",
        json={
            "system": "ata-rag",
            "dataset_version": "v1",
            "dataset_path": "synthetic.json",
            "application_version": "test",
        },
    )

    assert response.status_code == 200
    assert response.json()["experiment_id"] == "api-integration"
    assert calls[0][1] is registry


def test_observability_sidecar_does_not_pollute_experiment_listing(tmp_path, monkeypatch):
    experiment_dir = tmp_path / "experiments"
    experiment_dir.mkdir()
    (experiment_dir / "exp-1.json").write_text("{}", encoding="utf-8")
    observability_dir = tmp_path / "observability"
    observability_dir.mkdir()
    (observability_dir / "exp-1.json").write_text(
        json.dumps({"experiment_id": "exp-1", "enabled": False}),
        encoding="utf-8",
    )

    assert list_experiments(experiment_dir) == ["exp-1"]