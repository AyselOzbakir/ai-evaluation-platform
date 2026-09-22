from pathlib import Path


def test_generated_runtime_directories_are_ignored():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "artifacts/observability/" in gitignore
    assert "artifacts/human_evaluations/" in gitignore