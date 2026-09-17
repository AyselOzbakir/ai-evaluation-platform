import pytest

from app.experiments.rules import load_metric_rules


def test_load_metric_rules(tmp_path):
    rules_file = tmp_path / "regression_rules.yaml"
    rules_file.write_text(
        """
metrics:
  correctness_avg_score:
    direction: higher
    minimum: 0.90
    max_regression: 0.02
  case_error_rate:
    direction: lower
    maximum: 0.05
    max_regression: 0.02
""",
        encoding="utf-8",
    )

    rules = load_metric_rules(rules_file)

    assert rules["correctness_avg_score"].minimum == 0.90
    assert rules["correctness_avg_score"].direction == "higher"
    assert rules["case_error_rate"].maximum == 0.05
    assert rules["case_error_rate"].direction == "lower"


def test_invalid_direction_is_rejected(tmp_path):
    rules_file = tmp_path / "regression_rules.yaml"
    rules_file.write_text(
        "metrics:\n  correctness_avg_score:\n    direction: sideways\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid rule"):
        load_metric_rules(rules_file)


def test_missing_rules_file_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_metric_rules(tmp_path / "missing.yaml")