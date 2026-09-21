import json
import subprocess

import pytest

from app.core.models import EvaluationCase
from app.systems.report_reviewer.adapter import ReportReviewerAdapter


def make_case(**input_values):
    return EvaluationCase(
        id="report-review-test-001",
        system="report-reviewer",
        input={
            "report_text": "synthetic report text",
            "journal_text": "synthetic journal text",
            **input_values,
        },
    )


def valid_result(**overrides):
    result = {
        "status": "APPROVED",
        "score": 92,
        "summary": "Synthetic review.",
        "checks": [
            {
                "title": "Journal Dates",
                "status": "PASS",
                "message": "Dates found.",
                "evidence": "Week 1.",
            }
        ],
        "engine": "RULES",
    }
    result.update(overrides)
    return result


def mock_run(stdout, returncode=0, stderr="", calls=None):
    def run(command, **kwargs):
        if calls is not None:
            calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return run


def test_builds_isolated_python_command_and_normalizes_output(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setattr(
        "app.systems.report_reviewer.adapter.subprocess.run",
        mock_run(json.dumps(valid_result()), calls=calls),
    )

    adapter = ReportReviewerAdapter(
        reviewer_path=tmp_path,
        python_executable="/external/python",
    )
    result = adapter.run(make_case())

    command, kwargs = calls[0]
    assert command[0:2] == ["/external/python", "-c"]
    assert command[3] == str(tmp_path)
    assert command[4:] == ["synthetic report text", "synthetic journal text"]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert result.output["system"] == "internship-report-reviewer"
    assert result.output["status"] == "APPROVED"
    assert result.metadata["source"] == "external-internship-report-reviewer"
    assert isinstance(result.metadata["latency_ms"], int)


def test_missing_reviewer_path_is_rejected(monkeypatch):
    monkeypatch.delenv("REPORT_REVIEWER_PATH", raising=False)

    with pytest.raises(ValueError, match="path is not configured"):
        ReportReviewerAdapter().run(make_case())


def test_missing_required_input_is_rejected(tmp_path):
    case = EvaluationCase(
        id="missing",
        system="report-reviewer",
        input={"report_text": "only report"},
    )

    with pytest.raises(ValueError, match="journal_text"):
        ReportReviewerAdapter(reviewer_path=tmp_path).run(case)


def test_invalid_json_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.systems.report_reviewer.adapter.subprocess.run",
        mock_run("not json"),
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        ReportReviewerAdapter(reviewer_path=tmp_path).run(make_case())


def test_subprocess_failure_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.systems.report_reviewer.adapter.subprocess.run",
        mock_run("", returncode=3, stderr="reviewer failed"),
    )

    with pytest.raises(RuntimeError, match="exit code 3: reviewer failed"):
        ReportReviewerAdapter(reviewer_path=tmp_path).run(make_case())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "UNKNOWN", "invalid status"),
        ("score", 101, "between 0 and 100"),
        ("checks", {}, "checks must be a list"),
        (
            "checks",
            [{"title": "Dates", "status": "MAYBE", "message": "x", "evidence": "y"}],
            "invalid status",
        ),
    ],
)
def test_invalid_output_fields_are_rejected(
    tmp_path,
    monkeypatch,
    field,
    value,
    message,
):
    result = valid_result(**{field: value})
    monkeypatch.setattr(
        "app.systems.report_reviewer.adapter.subprocess.run",
        mock_run(json.dumps(result)),
    )

    with pytest.raises(ValueError, match=message):
        ReportReviewerAdapter(reviewer_path=tmp_path).run(make_case())


def test_ai_error_is_preserved_in_output_and_metadata(tmp_path, monkeypatch):
    result = valid_result(ai_error="synthetic provider failure")
    monkeypatch.setattr(
        "app.systems.report_reviewer.adapter.subprocess.run",
        mock_run(json.dumps(result)),
    )

    output = ReportReviewerAdapter(reviewer_path=tmp_path).run(make_case())

    assert output.output["ai_error"] == "synthetic provider failure"
    assert output.metadata["ai_error"] == "synthetic provider failure"