"""Adapter for the external Agentic Internship Coordinator pipeline."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.core.models import EvaluationCase, SystemAdapter, SystemOutput

ALLOWED_RECOMMENDATIONS = {
    "APPROVE",
    "REJECT",
    "REQUEST CLARIFICATION",
}

_BRIDGE_SCRIPT = """
import json
import sys

sys.path.insert(0, sys.argv[1])
from main import run_pipeline

result = run_pipeline(sys.argv[2], sys.argv[3])
print(json.dumps(result))
"""


class InternshipCoordinatorAdapter(SystemAdapter):
    """Invoke the external coordinator pipeline in an isolated process."""

    def __init__(
        self,
        coordinator_path: str | Path | None = None,
        python_executable: str | Path | None = None,
    ) -> None:
        self.coordinator_path = coordinator_path
        self.python_executable = str(
            python_executable
            if python_executable is not None
            else os.environ.get("INTERNSHIP_COORDINATOR_PYTHON") or sys.executable
        )

    def run(self, case: EvaluationCase) -> SystemOutput:
        coordinator_path = self._configured_coordinator_path()
        pdf_path = self._required_input(case, "pdf_path")
        student_email = self._required_input(case, "student_email")
        command = [
            self.python_executable,
            "-c",
            _BRIDGE_SCRIPT,
            str(coordinator_path),
            pdf_path,
            student_email,
        ]

        started = time.perf_counter()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(coordinator_path),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or "no error details"
            raise RuntimeError(
                f"Internship Coordinator process failed with exit code "
                f"{completed.returncode}: {detail}"
            )

        response = self._parse_response(completed.stdout)
        output = self._normalize_response(response)
        return SystemOutput(
            output=output,
            metadata={
                "source": "external-agentic-internship-coordinator",
                "latency_ms": latency_ms,
            },
        )

    def _configured_coordinator_path(self) -> Path:
        configured_path = self.coordinator_path or os.environ.get(
            "INTERNSHIP_COORDINATOR_PATH"
        )
        if not configured_path:
            raise ValueError(
                "Internship Coordinator path is not configured; provide "
                "coordinator_path or set INTERNSHIP_COORDINATOR_PATH."
            )

        coordinator_path = Path(configured_path)
        if not coordinator_path.is_dir():
            raise ValueError(
                "Internship Coordinator path does not exist or is not a directory: "
                f"{coordinator_path}"
            )
        return coordinator_path

    @staticmethod
    def _required_input(case: EvaluationCase, name: str) -> str:
        value = case.input.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Internship Coordinator input requires {name!r}.")
        return value

    @staticmethod
    def _parse_response(stdout: str) -> dict[str, Any]:
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Internship Coordinator returned invalid JSON: {exc.msg}."
            ) from exc
        if not isinstance(response, dict):
            raise RuntimeError(
                "Internship Coordinator returned JSON that was not an object."
            )
        return response

    @classmethod
    def _normalize_response(cls, response: dict[str, Any]) -> dict[str, Any]:
        if "decision" not in response:
            raise ValueError("Internship Coordinator response is missing decision.")
        if response.get("decision") != "PENDING":
            raise ValueError(
                "Internship Coordinator decision must be the human state 'PENDING'."
            )

        notes = response.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            raise ValueError(
                "Internship Coordinator response requires non-empty notes."
            )

        case_id = response.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(
                "Internship Coordinator response requires a non-empty case_id."
            )

        return {
            "system": "internship-coordinator",
            "recommendation": extract_recommendation(notes),
            "external_decision": "PENDING",
            "notes": notes,
            "case_id": case_id,
        }


def extract_recommendation(notes: str) -> str:
    """Extract one canonical recommendation from coordinator notes."""
    normalized = re.sub(r"\s+", " ", notes.upper()).strip()
    label_pattern = r"APPROVE|REJECT|REQUEST\s+CLARIFICATION"
    declaration_pattern = re.compile(
        rf"\b(?:RECOMMENDATION|RECOMMENDED)\s*:\s*({label_pattern})\b"
    )
    declared = [match.group(1).replace("  ", " ") for match in declaration_pattern.finditer(normalized)]
    candidates = declared or [
        match.group(1).replace("  ", " ")
        for match in re.finditer(rf"(?<![A-Z])({label_pattern})(?![A-Z])", normalized)
    ]
    candidates = list(dict.fromkeys(candidates))

    if len(candidates) > 1:
        raise RuntimeError(
            "Internship Coordinator notes contain conflicting recommendations: "
            f"{', '.join(candidates)}."
        )
    if not candidates:
        raise RuntimeError(
            "Internship Coordinator notes contain no recognized recommendation."
        )
    return candidates[0]