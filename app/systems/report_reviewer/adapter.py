"""Adapter for the external Internship Report Reviewer service."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.core.models import EvaluationCase, SystemAdapter, SystemOutput

ALLOWED_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REJECTED"}
ALLOWED_CHECK_STATUSES = {"PASS", "WARNING", "FAIL"}

_BRIDGE_SCRIPT = """
import json
import sys

sys.path.insert(0, sys.argv[1])
from services.reviewer import compare_documents

result = compare_documents(sys.argv[2], sys.argv[3])
print(json.dumps(result))
"""


class ReportReviewerAdapter(SystemAdapter):
    """Invoke ``services.reviewer.compare_documents`` in an external process."""

    def __init__(
        self,
        reviewer_path: str | Path | None = None,
        python_executable: str | Path | None = None,
        deterministic: bool = True,
    ) -> None:
        self.reviewer_path = reviewer_path
        self.python_executable = str(
            python_executable
            if python_executable is not None
            else os.environ.get("REPORT_REVIEWER_PYTHON") or sys.executable
        )
        self.deterministic = deterministic

    def run(self, case: EvaluationCase) -> SystemOutput:
        reviewer_path = self._configured_reviewer_path()
        report_text = self._required_text(case, "report_text")
        journal_text = self._required_text(case, "journal_text")

        environment = os.environ.copy()
        if self.deterministic:
            environment.pop("OPENAI_API_KEY", None)

        command = [
            self.python_executable,
            "-c",
            _BRIDGE_SCRIPT,
            str(reviewer_path),
            report_text,
            journal_text,
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(reviewer_path),
            env=environment,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or "no error details"
            raise RuntimeError(
                f"Report Reviewer process failed with exit code "
                f"{completed.returncode}: {detail}"
            )

        result = self._parse_result(completed.stdout)
        output, ai_error = self._normalize_result(result)
        metadata: dict[str, Any] = {
            "source": "external-internship-report-reviewer",
            "latency_ms": latency_ms,
        }
        if ai_error is not None:
            metadata["ai_error"] = ai_error

        return SystemOutput(output=output, metadata=metadata)

    def _configured_reviewer_path(self) -> Path:
        configured_path = self.reviewer_path or os.environ.get(
            "REPORT_REVIEWER_PATH"
        )
        if not configured_path:
            raise ValueError(
                "Report Reviewer path is not configured; provide reviewer_path or "
                "set REPORT_REVIEWER_PATH."
            )

        reviewer_path = Path(configured_path)
        if not reviewer_path.is_dir():
            raise ValueError(
                f"Report Reviewer path does not exist or is not a directory: "
                f"{reviewer_path}"
            )
        return reviewer_path

    @staticmethod
    def _required_text(case: EvaluationCase, name: str) -> str:
        value = case.input.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Report Reviewer input requires non-empty {name!r}.")
        return value

    @staticmethod
    def _parse_result(stdout: str) -> dict[str, Any]:
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Report Reviewer returned invalid JSON: {exc.msg}."
            ) from exc
        if not isinstance(result, dict):
            raise RuntimeError("Report Reviewer returned JSON that was not an object.")
        return result

    @staticmethod
    def _normalize_result(
        result: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        status = result.get("status")
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                "Report Reviewer returned invalid status; expected one of "
                f"{sorted(ALLOWED_STATUSES)}."
            )

        score = result.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("Report Reviewer score must be numeric.")
        if not 0 <= score <= 100:
            raise ValueError("Report Reviewer score must be between 0 and 100.")

        summary = result.get("summary")
        if not isinstance(summary, str):
            raise ValueError("Report Reviewer summary must be a string.")

        checks = result.get("checks")
        if not isinstance(checks, list):
            raise ValueError("Report Reviewer checks must be a list.")
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                raise ValueError(f"Report Reviewer check {index} must be an object.")
            for field in ("title", "message", "evidence"):
                if not isinstance(check.get(field), str):
                    raise ValueError(
                        f"Report Reviewer check {index} field {field!r} must be a string."
                    )
            if check.get("status") not in ALLOWED_CHECK_STATUSES:
                raise ValueError(
                    f"Report Reviewer check {index} has invalid status; expected one of "
                    f"{sorted(ALLOWED_CHECK_STATUSES)}."
                )

        output = {
            "system": "internship-report-reviewer",
            "status": status,
            "score": score,
            "summary": summary,
            "checks": checks,
            "engine": result.get("engine", "unknown"),
        }
        ai_error = result.get("ai_error")
        if ai_error is not None:
            if not isinstance(ai_error, str):
                raise ValueError("Report Reviewer ai_error must be a string.")
            output["ai_error"] = ai_error

        return output, ai_error