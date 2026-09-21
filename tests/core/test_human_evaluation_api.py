import json

from fastapi.testclient import TestClient

from app.main import app


def test_human_evaluation_create_and_read(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "experiments"))
    experiment_dir = tmp_path / "experiments"
    experiment_dir.mkdir()
    (experiment_dir / "human-exp.json").write_text(
        json.dumps(
            {
                "experiment_id": "human-exp",
                "system": "fake",
                "dataset_version": "v1",
                "application_version": "app-v1",
                "started_at": "2026-09-22T00:00:00Z",
                "case_results": [{"case_id": "case-1", "evaluations": []}],
                "aggregate_metrics": {},
                "passed": True,
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.post(
        "/human-evaluations",
        json={
            "experiment_id": "human-exp",
            "case_id": "case-1",
            "evaluator_name": "reviewer",
            "score": 0.75,
            "comment": "Needs a second look.",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["comment"] == "Needs a second look."

    second = client.post(
        "/human-evaluations",
        json={
            "experiment_id": "human-exp",
            "case_id": "case-1",
            "evaluator_name": "reviewer-2",
            "passed": False,
            "label": "review",
        },
    )
    assert second.status_code == 201
    listed = client.get("/human-evaluations/human-exp")
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_human_evaluation_rejects_unknown_experiment(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "experiments"))

    response = TestClient(app).post(
        "/human-evaluations",
        json={
            "experiment_id": "missing",
            "case_id": "case-1",
            "evaluator_name": "reviewer",
            "passed": True,
        },
    )
    assert response.status_code == 400