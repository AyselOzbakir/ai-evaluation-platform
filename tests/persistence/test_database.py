from app.core.experiment import ExperimentResult
from app.persistence.database import create_repository


def test_sqlalchemy_repository_persists_experiment_and_human_evaluation(tmp_path):
    repository = create_repository(f"sqlite:///{tmp_path / 'test.db'}")
    experiment = ExperimentResult(
        experiment_id="db-exp",
        system="fake",
        dataset_version="v1",
        application_version="app-v1",
        started_at="2026-09-22T00:00:00Z",
    )

    repository.save_experiment(experiment)
    evaluation = repository.add_human_evaluation(
        {
            "experiment_id": "db-exp",
            "case_id": "case-1",
            "evaluator_name": "reviewer@example.test",
            "score": 0.8,
            "passed": True,
            "label": "good",
            "comment": "Looks correct.",
            "metadata": {"source": "test"},
            "created_at": __import__("datetime").datetime.now(__import__("datetime").UTC),
        }
    )

    assert evaluation["experiment_id"] == "db-exp"
    assert repository.list_human_evaluations("db-exp")[0]["comment"] == "Looks correct."