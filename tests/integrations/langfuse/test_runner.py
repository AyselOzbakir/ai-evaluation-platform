import json

from app.core.config import RunConfig
from app.core.registry import Registry
from app.core.runner import run_experiment
from app.integrations.langfuse.runner import run_experiment_with_langfuse
from tests.core.fakes import FakeAdapter, FakeEvaluator


class FakeTrace:
    enabled = True
    trace_id = "trace-123"
    observation_id = "observation-123"

    def __init__(self):
        self.updated = []
        self.ended = False

    def start_observation(self, name, metadata, input_data=None):
        return FakeTrace()

    def update(self, **kwargs):
        self.updated.append(kwargs)

    def end(self):
        self.ended = True

    def flush(self):
        return None


class FakeLangfuse:
    enabled = True
    trace_id = "trace-123"
    base_url = "https://langfuse.example"
    project_id = "project-1"

    def __init__(self):
        self.started = []
        self.dataset = FakeDataset()

    def start_trace(self, name, metadata, input_data=None):
        self.started.append((name, metadata, input_data))
        return FakeTrace()

    def get_dataset(self, name):
        self.dataset.name = name
        return self.dataset

    def run_dataset_experiment(self, dataset, **kwargs):
        return dataset.run_experiment(**kwargs)


class FakeDataset:
    def __init__(self):
        self.name = None
        self.calls = []

    def run_experiment(self, **kwargs):
        self.calls.append(kwargs)
        item = type(
            "DatasetItem",
            (),
            {
                "id": "case-1",
                "input": {},
                "expected_output": {},
                "metadata": {"case_id": "case-1", "dataset_version": "v1"},
            },
        )()
        output = kwargs["task"](item=item)
        for evaluator in kwargs["evaluators"]:
            evaluator(
                input=item.input,
                output=output,
                expected_output=item.expected_output,
                metadata=item.metadata,
            )
        return {
            "dataset_run_id": "dataset-run-1",
            "dataset_run_url": "https://langfuse.example/dataset-run-1",
        }


class DisabledFake:
    enabled = False
    trace_id = None

    def flush(self):
        raise AssertionError("disabled client should not be flushed through root")


def make_config(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        '[{"id":"case-1","system":"fake","input":{}}]',
        encoding="utf-8",
    )
    return RunConfig(
        system="fake",
        dataset_version="v1",
        dataset_path=str(dataset),
        evaluators=["fake_exact_match"],
        application_version="app-v1",
    )


def make_registry():
    registry = Registry()
    registry.register_adapter("fake", FakeAdapter())
    registry.register_evaluator("fake_exact_match", FakeEvaluator())
    return registry


def test_disabled_wrapper_preserves_experiment_result_and_writes_disabled_sidecar(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    config = make_config(tmp_path)

    wrapped = run_experiment_with_langfuse(
        config,
        make_registry(),
        experiment_id="exp-disabled",
        client=DisabledFake(),
        persist=False,
    )

    direct = run_experiment(config, make_registry(), experiment_id="exp-disabled", persist=False)
    assert wrapped.model_dump(exclude={"started_at"}) == direct.model_dump(exclude={"started_at"})
    sidecar = tmp_path / "observability" / "exp-disabled.json"
    assert json.loads(sidecar.read_text()) == {
        "experiment_id": "exp-disabled",
        "enabled": False,
    }


def test_enabled_fake_client_receives_root_lifecycle_and_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    client = FakeLangfuse()
    result = run_experiment_with_langfuse(
        make_config(tmp_path),
        make_registry(),
        experiment_id="exp-enabled",
        client=client,
        persist=False,
    )

    assert result.experiment_id == "exp-enabled"
    assert client.started[0][1]["experiment_id"] == "exp-enabled"
    sidecar = json.loads(
        (tmp_path / "observability" / "exp-enabled.json").read_text()
    )
    assert sidecar == {
        "experiment_id": "exp-enabled",
        "enabled": True,
        "langfuse_trace_id": "trace-123",
        "langfuse_trace_url": "https://langfuse.example/project/project-1/traces/trace-123",
    }


def test_wrapper_generated_id_matches_sidecar_and_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    result = run_experiment_with_langfuse(
        make_config(tmp_path),
        make_registry(),
        client=DisabledFake(),
    )

    artifact = tmp_path / "artifacts" / f"{result.experiment_id}.json"
    sidecar = tmp_path / "observability" / f"{result.experiment_id}.json"
    assert artifact.exists()
    assert sidecar.exists()
    assert json.loads(sidecar.read_text())["experiment_id"] == result.experiment_id


def test_wrapper_associates_dataset_run_when_prefix_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LANGFUSE_DATASET_PREFIX", "golden")
    client = FakeLangfuse()

    result = run_experiment_with_langfuse(
        make_config(tmp_path),
        make_registry(),
        experiment_id="dataset-exp",
        client=client,
        persist=False,
    )

    assert result.experiment_id == "dataset-exp"
    assert client.dataset.name == "golden-fake"
    assert client.dataset.calls[0]["run_name"] == "dataset-exp"
    assert result.metadata["langfuse_dataset_run_id"] == "dataset-run-1"
    assert result.metadata["langfuse_dataset_run_url"] == "https://langfuse.example/dataset-run-1"