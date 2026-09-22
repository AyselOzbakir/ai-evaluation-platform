import json

import pytest

from app.core.config import RunConfig
from app.core.registry import Registry
from app.core.runner import run_experiment
from app.core.storage import list_experiments, load_experiment
from app.experiments.comparison import compare_experiments
from tests.core.fakes import CrashingEvaluator, FakeAdapter, FakeEvaluator


def _write_dataset(tmp_path, cases: list[dict]) -> str:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    return str(path)


def _registry() -> Registry:
    reg = Registry()
    reg.register_adapter("fake", FakeAdapter())
    reg.register_evaluator("fake_exact_match", FakeEvaluator())
    reg.register_evaluator("crashing_evaluator", CrashingEvaluator())
    return reg


def test_end_to_end_run_produces_experiment_json(tmp_path):
    dataset_path = _write_dataset(
        tmp_path,
        [
            {"id": "c1", "system": "fake", "input": {"q": "hi"}, "expected_output": {"q": "hi"}},
            {"id": "c2", "system": "fake", "input": {"q": "bye"}, "expected_output": {"q": "nope"}},
        ],
    )
    config = RunConfig(
        system="fake",
        dataset_version="fake-v1",
        dataset_path=dataset_path,
        evaluators=["fake_exact_match"],
    )
    artifact_dir = tmp_path / "artifacts"

    experiment = run_experiment(
        config, _registry(), experiment_id="test-exp", persist=False
    )

    assert experiment.experiment_id == "test-exp"
    assert len(experiment.case_results) == 2
    assert experiment.aggregate_metrics["fake_exact_match_avg_score"] == 0.5
    assert experiment.aggregate_metrics["fake_exact_match_pass_rate"] == 0.5
    assert not artifact_dir.exists()  # persist=False must not write anything


def test_persist_writes_json_file(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    dataset_path = _write_dataset(
        tmp_path,
        [{"id": "c1", "system": "fake", "input": {"q": "hi"}, "expected_output": {"q": "hi"}}],
    )
    config = RunConfig(
        system="fake", dataset_version="fake-v1", dataset_path=dataset_path,
        evaluators=["fake_exact_match"],
    )

    experiment = run_experiment(config, _registry(), experiment_id="persisted-exp")

    saved_path = tmp_path / "artifacts" / "persisted-exp.json"
    assert saved_path.exists()
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert saved["experiment_id"] == experiment.experiment_id


def test_optional_version_metadata_is_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    dataset_path = _write_dataset(
        tmp_path,
        [{"id": "c1", "system": "fake", "input": {"q": "hi"}}],
    )
    config = RunConfig(
        system="fake",
        dataset_version="v1",
        dataset_path=dataset_path,
        evaluators=["fake_exact_match"],
        model_version="model-v1",
        model_name="synthetic-model",
        prompt_version="prompt-v1",
        config_version="config-v1",
        evaluator_versions={"fake_exact_match": "evaluator-v1"},
    )

    experiment = run_experiment(config, _registry())
    saved = json.loads(
        (tmp_path / "artifacts" / f"{experiment.experiment_id}.json").read_text()
    )

    assert saved["metadata"]["model_version"] == "model-v1"
    assert saved["metadata"]["prompt_version"] == "prompt-v1"
    assert saved["metadata"]["evaluator_names"] == ["fake_exact_match"]


def test_consecutive_runs_create_distinct_retrievable_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    dataset_path = _write_dataset(
        tmp_path,
        [{"id": "c1", "system": "fake", "input": {"q": "hi"}}],
    )
    config_v1 = RunConfig(
        system="fake",
        dataset_version="v1",
        dataset_path=dataset_path,
        application_version="demo-v1",
    )
    config_v2 = config_v1.model_copy(update={"application_version": "demo-v2"})

    first = run_experiment(config_v1, _registry())
    second = run_experiment(config_v2, _registry())

    assert first.experiment_id != second.experiment_id
    assert first.experiment_id < second.experiment_id
    assert list_experiments() == sorted([first.experiment_id, second.experiment_id])
    assert load_experiment(first.experiment_id).application_version == "demo-v1"
    assert load_experiment(second.experiment_id).application_version == "demo-v2"
    comparison = compare_experiments(
        load_experiment(first.experiment_id),
        load_experiment(second.experiment_id),
    )
    assert comparison.baseline_id == first.experiment_id
    assert comparison.candidate_id == second.experiment_id


def test_existing_artifact_collision_fails_instead_of_overwriting(tmp_path):
    from app.core.experiment import ExperimentResult
    from app.core.storage import save_experiment

    experiment = ExperimentResult(
        experiment_id="manual-id",
        system="fake",
        dataset_version="v1",
        application_version="demo-v1",
        started_at="2026-09-22T00:00:00Z",
    )
    save_experiment(experiment, directory=tmp_path)

    with pytest.raises(FileExistsError):
        save_experiment(
            experiment.model_copy(update={"application_version": "demo-v2"}),
            directory=tmp_path,
        )


def test_adapter_failure_is_captured_not_raised(tmp_path):
    dataset_path = _write_dataset(
        tmp_path, [{"id": "boom-1", "system": "fake", "input": {"q": "hi"}}]
    )
    config = RunConfig(
        system="fake", dataset_version="fake-v1", dataset_path=dataset_path, evaluators=[]
    )

    experiment = run_experiment(config, _registry(), experiment_id="boom-exp", persist=False)

    assert len(experiment.case_results) == 1
    assert experiment.case_results[0].error is not None
    assert not experiment.passed


def test_evaluator_crash_is_captured_per_case(tmp_path):
    dataset_path = _write_dataset(
        tmp_path, [{"id": "c1", "system": "fake", "input": {"q": "hi"}}]
    )
    config = RunConfig(
        system="fake",
        dataset_version="fake-v1",
        dataset_path=dataset_path,
        evaluators=["crashing_evaluator"],
    )

    experiment = run_experiment(config, _registry(), experiment_id="crash-exp", persist=False)

    assert experiment.case_results[0].error is None
    assert experiment.case_results[0].evaluations[0].passed is False
    assert "crashed" in experiment.case_results[0].evaluations[0].reason


def test_threshold_failure_marks_experiment_failed(tmp_path):
    dataset_path = _write_dataset(
        tmp_path,
        [{"id": "c1", "system": "fake", "input": {"q": "hi"}, "expected_output": {"q": "nope"}}],
    )
    config = RunConfig(
        system="fake",
        dataset_version="fake-v1",
        dataset_path=dataset_path,
        evaluators=["fake_exact_match"],
        thresholds={"fake_exact_match": 0.9},
    )

    experiment = run_experiment(config, _registry(), experiment_id="threshold-exp", persist=False)

    assert not experiment.passed
