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

    def start_trace(self, name, metadata, input_data=None):
        self.started.append((name, metadata, input_data))
        return FakeTrace()


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