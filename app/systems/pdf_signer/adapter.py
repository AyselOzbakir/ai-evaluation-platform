"""Adapter for the external Orange PDF Signer command-line backend."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.models import EvaluationCase, SystemAdapter, SystemOutput


class PDFSignerAdapter(SystemAdapter):
    """Run deterministic PDF detection and placement commands."""

    def __init__(
        self,
        backend_path: str | Path | None = None,
        python_executable: str | Path | None = None,
    ) -> None:
        self.backend_path = backend_path
        resolved_python = (
            python_executable
            if python_executable is not None
            else os.environ.get("PDF_SIGNER_PYTHON") or sys.executable
        )
        self.python_executable = str(resolved_python)

    def run(self, case: EvaluationCase) -> SystemOutput:
        backend_path = self._configured_backend_path()
        operation = case.input.get("operation", "detect")

        if operation == "detect":
            return self._detect(case, backend_path)
        if operation == "place":
            return self._place(case, backend_path)
        raise ValueError(
            f"Unsupported PDF Signer operation: {operation!r}; expected 'detect' or 'place'."
        )

    def _configured_backend_path(self) -> Path:
        configured_path = self.backend_path or os.environ.get(
            "PDF_SIGNER_BACKEND_PATH"
        )
        if not configured_path:
            raise ValueError(
                "PDF Signer backend is not configured; provide backend_path or set "
                "PDF_SIGNER_BACKEND_PATH."
            )

        backend_path = Path(configured_path)
        if not backend_path.is_file():
            raise ValueError(
                f"PDF Signer backend file does not exist: {backend_path}"
            )
        return backend_path

    def _detect(
        self,
        case: EvaluationCase,
        backend_path: Path,
    ) -> SystemOutput:
        pdf_path = self._required_input(case, "pdf_path")
        page_number = self._page_number(case)
        command = [
            self.python_executable,
            str(backend_path),
            "detect",
            pdf_path,
            str(page_number),
        ]
        completed = self._run_command(command)

        try:
            areas = _extract_json_payload(completed.stdout)
        except ValueError as exc:
            raise RuntimeError(
                f"PDF Signer detect returned invalid JSON: {exc}."
            ) from exc

        if not isinstance(areas, list):
            raise RuntimeError("PDF Signer detect returned JSON that was not a list.")

        return SystemOutput(
            output={
                "operation": "detect",
                "page_number": page_number,
                "areas": areas,
            },
            metadata={"returncode": completed.returncode},
        )

    def _place(
        self,
        case: EvaluationCase,
        backend_path: Path,
    ) -> SystemOutput:
        pdf_path = self._required_input(case, "pdf_path")
        page_number = self._page_number(case)
        x = self._required_number(case, "x")
        y = self._required_number(case, "y")
        signature_image_path = self._required_input(
            case, "signature_image_path"
        )
        width = self._number_or_default(case, "width", 150)
        height = self._number_or_default(case, "height", 60)
        requested_output_path = case.input.get("output_path")

        command = [
            self.python_executable,
            str(backend_path),
            "place",
            pdf_path,
            str(page_number),
            str(x),
            str(y),
            signature_image_path,
            "--width",
            str(width),
            "--height",
            str(height),
        ]
        if requested_output_path:
            command.extend(["--output", str(requested_output_path)])

        completed = self._run_command(command)
        stdout_path = _extract_output_path(completed.stdout)
        output_path = str(requested_output_path or stdout_path)

        return SystemOutput(
            output={
                "operation": "place",
                "page_number": page_number,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "output_path": output_path,
            },
            metadata={
                "returncode": completed.returncode,
                "stdout_path": stdout_path,
            },
        )

    @staticmethod
    def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "no error details"
            raise RuntimeError(
                f"PDF Signer command failed with exit code "
                f"{completed.returncode}: {detail}"
            )
        return completed

    @staticmethod
    def _required_input(case: EvaluationCase, name: str) -> str:
        value = case.input.get(name)
        if value is None or str(value).strip() == "":
            raise ValueError(f"PDF Signer input requires {name!r}.")
        return str(value)

    @staticmethod
    def _page_number(case: EvaluationCase) -> int:
        value = case.input.get("page_number")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("PDF Signer input requires integer 'page_number'.")
        return value

    @staticmethod
    def _required_number(case: EvaluationCase, name: str) -> int | float:
        value = case.input.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"PDF Signer input requires numeric {name!r}.")
        return value

    @classmethod
    def _number_or_default(
        cls,
        case: EvaluationCase,
        name: str,
        default: int,
    ) -> int | float:
        if name not in case.input:
            return default
        return cls._required_number(case, name)


def _extract_json_payload(stdout: str) -> Any:
    decoder = json.JSONDecoder()

    for index, character in enumerate(stdout):
        if character not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, (list, dict)):
            return payload

    raise ValueError("no valid JSON list or object found in stdout")


def _extract_output_path(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        path = line.strip()
        if path:
            return path

    raise RuntimeError("PDF Signer place returned no output PDF path.")