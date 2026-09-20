from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.experiments.comparison import MetricRule


def load_metric_rules(path: str | Path) -> dict[str, MetricRule]:
    rules_path = Path(path)

    try:
        with rules_path.open(encoding="utf-8") as rules_file:
            config: Any = yaml.safe_load(rules_file)
    except FileNotFoundError as exc:
        raise ValueError(
            f"Regression rules file not found: {rules_path}"
        ) from exc
    except OSError as exc:
        raise ValueError(
            f"Could not read regression rules file {rules_path}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Invalid YAML in regression rules file {rules_path}: {exc}"
        ) from exc

    if not isinstance(config, dict) or not isinstance(
        config.get("metrics"), dict
    ):
        raise ValueError(
            f"Regression rules file {rules_path} must contain a metrics mapping."
        )

    metric_rules: dict[str, MetricRule] = {}
    for metric, rule_config in config["metrics"].items():
        if not isinstance(metric, str) or not isinstance(
            rule_config, dict
        ):
            raise ValueError(
                f"Invalid rule for metric {metric!r} in {rules_path}."
            )

        try:
            metric_rules[metric] = MetricRule.model_validate(
                rule_config
            )
        except ValidationError as exc:
            raise ValueError(
                f"Invalid rule for metric {metric!r} in {rules_path}: {exc}"
            ) from exc

    return metric_rules