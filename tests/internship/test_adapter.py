import json
import subprocess
import sys

import pytest

from app.core.models import EvaluationCase
from app.systems.internship.adapter import (
    InternshipCoordinatorAdapter,
    extract_recommendation,
)


def make_case(**input_values):
    return EvaluationCase(
        id="internship-test-001",
        system="internship-coordinator",
        input={
            "pdf_path": "synthetic/application.pdf",
            "student_email": "synthetic@example.test",
            **input_values,
        },
    )


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


def valid_response(**overrides):
    response = {
        "decision": "PENDING",
        "notes": "RECOMMENDATION: APPROVE\n[OK] Complete.\n[PASS] Compliant.",
        "case_id": "synthetic-case-001",
    }
    response.update(overrides)
    return response


def test_builds_isolated_command_and_normalizes_response(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.systems.internship.adapter.subprocess.run",
        mock_run(json.dumps(valid_response()), calls=calls),
    )

    result = InternshipCoordinatorAdapter(
        coordinator_path=tmp_path,
        python_executable="/external/python",
    ).run(make_case())

    command, kwargs = calls[0]
    assert command[0:2] == ["/external/python", "-c"]
    assert command[3:] == [
        str(tmp_path),
        "synthetic/application.pdf",
        "synthetic@example.test",
    ]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert result.output == {
        "system": "internship-coordinator",
        "recommendation": "APPROVE",
        "external_decision": "PENDING",
        "notes": valid_response()["notes"],
        "case_id": "synthetic-case-001",
    }
    assert result.metadata["source"] == "external-agentic-internship-coordinator"
    assert isinstance(result.metadata["latency_ms"], int)


def test_path_and_python_are_resolved_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERNSHIP_COORDINATOR_PATH", str(tmp_path))
    monkeypatch.setenv("INTERNSHIP_COORDINATOR_PYTHON", "/env/python")

    adapter = InternshipCoordinatorAdapter()

    assert adapter.coordinator_path is None
    assert adapter.python_executable == "/env/python"
    assert adapter._configured_coordinator_path() == tmp_path


def test_constructor_python_overrides_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERNSHIP_COORDINATOR_PYTHON", "/env/python")

    adapter = InternshipCoordinatorAdapter(
        coordinator_path=tmp_path,
        python_executable="/explicit/python",
    )

    assert adapter.python_executable == "/explicit/python"


def test_python_falls_back_to_sys_executable(tmp_path, monkeypatch):
    monkeypatch.delenv("INTERNSHIP_COORDINATOR_PYTHON", raising=False)

    adapter = InternshipCoordinatorAdapter(coordinator_path=tmp_path)

    assert adapter.python_executable == sys.executable


def test_missing_coordinator_path_is_rejected(monkeypatch):
    monkeypatch.delenv("INTERNSHIP_COORDINATOR_PATH", raising=False)

    with pytest.raises(ValueError, match="path is not configured"):
        InternshipCoordinatorAdapter().run(make_case())


@pytest.mark.parametrize("field", ["pdf_path", "student_email"])
def test_missing_required_input_is_rejected(tmp_path, field):
    with pytest.raises(ValueError, match=field):
        InternshipCoordinatorAdapter(coordinator_path=tmp_path).run(
            make_case(**{field: ""})
        )


def test_invalid_json_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.systems.internship.adapter.subprocess.run",
        mock_run("not json"),
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        InternshipCoordinatorAdapter(coordinator_path=tmp_path).run(make_case())


def test_subprocess_failure_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.systems.internship.adapter.subprocess.run",
        mock_run("", returncode=2, stderr="coordinator failed"),
    )

    with pytest.raises(RuntimeError, match="exit code 2: coordinator failed"):
        InternshipCoordinatorAdapter(coordinator_path=tmp_path).run(make_case())


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({"decision": "PENDING", "notes": "RECOMMENDATION: APPROVE"}, "case_id"),
        ({"decision": "PENDING", "case_id": "case"}, "notes"),
        ({"notes": "RECOMMENDATION: APPROVE", "case_id": "case"}, "decision"),
        ({"decision": "DONE", "notes": "RECOMMENDATION: APPROVE", "case_id": "case"}, "human state"),
    ],
)
def test_malformed_external_response_is_rejected(tmp_path, monkeypatch, response, message):
    monkeypatch.setattr(
        "app.systems.internship.adapter.subprocess.run",
        mock_run(json.dumps(response)),
    )

    with pytest.raises(ValueError, match=message):
        InternshipCoordinatorAdapter(coordinator_path=tmp_path).run(make_case())


@pytest.mark.parametrize(
    ("notes", "expected"),
    [
        ("RECOMMENDATION: approve", "APPROVE"),
        ("Recommendation: reject", "REJECT"),
        ("RECOMMENDATION: request   clarification", "REQUEST CLARIFICATION"),
    ],
)
def test_recommendation_labels_are_extracted(notes, expected):
    assert extract_recommendation(notes) == expected


def test_recommendation_does_not_match_rejected_substring():
    with pytest.raises(RuntimeError, match="no recognized"):
        extract_recommendation("The application was rejected by an unrelated prior process.")


def test_conflicting_recommendations_are_rejected():
    with pytest.raises(RuntimeError, match="conflicting"):
        extract_recommendation(
            "RECOMMENDATION: APPROVE\nRECOMMENDATION: REJECT"
        )


def test_notes_without_recommendation_are_rejected():
    with pytest.raises(RuntimeError, match="no recognized"):
        extract_recommendation("The application is complete and compliant.")