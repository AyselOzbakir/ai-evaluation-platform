from app.core.experiment import ExperimentResult
from app.core.storage import list_experiments, load_experiment, save_experiment


def _experiment(experiment_id: str) -> ExperimentResult:
    return ExperimentResult(
        experiment_id=experiment_id,
        system="fake",
        dataset_version="fake-v1",
        application_version="test",
        started_at="2026-01-01T00:00:00+00:00",
    )


def test_save_and_load_round_trip(tmp_path):
    experiment = _experiment("exp-1")
    save_experiment(experiment, directory=tmp_path)
    loaded = load_experiment("exp-1", directory=tmp_path)
    assert loaded == experiment


def test_list_experiments(tmp_path):
    save_experiment(_experiment("exp-a"), directory=tmp_path)
    save_experiment(_experiment("exp-b"), directory=tmp_path)
    assert list_experiments(tmp_path) == ["exp-a", "exp-b"]


def test_list_experiments_missing_dir_returns_empty(tmp_path):
    assert list_experiments(tmp_path / "does-not-exist") == []
