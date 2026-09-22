from app.integrations.langfuse.metadata import (
    METADATA_KEYS,
    evaluation_metadata,
    observability_sidecar,
    trace_url,
)


def test_evaluation_metadata_uses_stable_keys_only():
    metadata = evaluation_metadata(
        experiment_id="exp",
        system="system",
        dataset_version="v1",
        application_version="app-v1",
        case_id="case",
        evaluator="quality",
        secret="must-not-appear",
    )

    assert set(metadata).issubset(METADATA_KEYS)
    assert set(metadata) == {
        "experiment_id",
        "system",
        "dataset_version",
        "application_version",
        "case_id",
        "evaluator",
    }
    assert "secret" not in metadata


def test_optional_version_metadata_is_propagated():
    metadata = evaluation_metadata(
        experiment_id="exp",
        model_version="model-v1",
        prompt_version="prompt-v1",
        config_version="config-v1",
        evaluator_names=["quality"],
    )

    assert metadata["model_version"] == "model-v1"
    assert metadata["prompt_version"] == "prompt-v1"
    assert metadata["evaluator_names"] == ["quality"]


def test_trace_url_normalizes_trailing_slashes():
    assert trace_url("https://langfuse.example///", "project", "trace") == (
        "https://langfuse.example/project/project/traces/trace"
    )


def test_trace_url_requires_project_and_trace_ids():
    assert trace_url("https://example", None, "trace") is None
    assert trace_url("https://example", "project", None) is None


def test_sidecar_omits_missing_trace_fields():
    assert observability_sidecar("exp", False) == {
        "experiment_id": "exp",
        "enabled": False,
    }