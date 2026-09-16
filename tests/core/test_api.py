import json

from fastapi.testclient import TestClient

from app.core.registry import registry
from app.main import app
from tests.core.fakes import FakeAdapter, FakeEvaluator

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_systems_lists_registered_adapters():
    registry.register_adapter("api-test-fake", FakeAdapter())
    response = client.get("/systems")
    assert "api-test-fake" in response.json()


def test_run_evaluation_then_fetch_it(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path))
    registry.register_adapter("api-test-fake", FakeAdapter())
    registry.register_evaluator("api-test-eval", FakeEvaluator())

    dataset_path = tmp_path / "cases.json"
    dataset_path.write_text(
        json.dumps([{"id": "c1", "system": "api-test-fake", "input": {"q": "hi"}}]),
        encoding="utf-8",
    )

    run_response = client.post(
        "/evaluations/run",
        json={
            "system": "api-test-fake",
            "dataset_version": "v1",
            "dataset_path": str(dataset_path),
            "evaluators": ["api-test-eval"],
        },
    )
    assert run_response.status_code == 200, run_response.text
    experiment_id = run_response.json()["experiment_id"]

    fetch_response = client.get(f"/evaluations/{experiment_id}")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["experiment_id"] == experiment_id

    via_experiments = client.get(f"/experiments/{experiment_id}")
    assert via_experiments.status_code == 200

    listing = client.get("/experiments")
    assert experiment_id in listing.json()


def test_run_evaluation_unknown_system_returns_400(tmp_path):
    dataset_path = tmp_path / "cases.json"
    dataset_path.write_text(
        json.dumps([{"id": "c1", "system": "nope", "input": {}}]), encoding="utf-8"
    )
    response = client.post(
        "/evaluations/run",
        json={
            "system": "does-not-exist",
            "dataset_version": "v1",
            "dataset_path": str(dataset_path),
        },
    )
    assert response.status_code == 400


def test_get_missing_experiment_returns_404():
    response = client.get("/evaluations/no-such-experiment")
    assert response.status_code == 404
