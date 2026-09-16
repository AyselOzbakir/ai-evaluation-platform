import pytest

from app.core.config import ConfigError, load_run_config


def test_load_valid_config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
system: fake
dataset_version: fake-v1
dataset_path: datasets/fake/cases.json
evaluators:
  - fake_exact_match
thresholds:
  fake_exact_match: 0.9
""",
        encoding="utf-8",
    )
    config = load_run_config(path)
    assert config.system == "fake"
    assert config.evaluators == ["fake_exact_match"]
    assert config.thresholds == {"fake_exact_match": 0.9}
    assert config.application_version == "unknown"


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_run_config(tmp_path / "missing.yaml")


def test_missing_required_field_raises(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("system: fake\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_run_config(path)


def test_non_mapping_yaml_raises(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_run_config(path)
