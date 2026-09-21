import json

from fastapi.testclient import TestClient

from app.main import app


def test_observability_sidecar_is_exposed_safely(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "experiments"))
    sidecar_dir = tmp_path / "observability"
    sidecar_dir.mkdir()
    (sidecar_dir / "exp-1.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-1",
                "enabled": True,
                "langfuse_trace_id": "trace-1",
                "langfuse_trace_url": "https://example.test/trace-1",
                "langfuse_observation_id": "observation-1",
                "secret_key": "must-not-leak",
            }
        ),
        encoding="utf-8",
    )

    response = TestClient(app).get("/dashboard/observability/exp-1")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "exp-1",
        "enabled": True,
        "langfuse_trace_id": "trace-1",
        "langfuse_trace_url": "https://example.test/trace-1",
        "langfuse_observation_id": "observation-1",
    }


def test_missing_sidecar_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "experiments"))

    response = TestClient(app).get("/dashboard/observability/missing")

    assert response.status_code == 200
    assert response.json() == {"experiment_id": "missing", "enabled": False}


def test_disabled_sidecar_is_returned_without_trace_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "experiments"))
    sidecar_dir = tmp_path / "observability"
    sidecar_dir.mkdir()
    (sidecar_dir / "exp-disabled.json").write_text(
        json.dumps({"experiment_id": "exp-disabled", "enabled": False}),
        encoding="utf-8",
    )

    response = TestClient(app).get("/dashboard/observability/exp-disabled")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "exp-disabled",
        "enabled": False,
    }


def test_path_traversal_experiment_id_is_rejected():
    response = TestClient(app).get("/dashboard/observability/%2E%2E%2Fsecret")

    assert response.status_code in {400, 404}