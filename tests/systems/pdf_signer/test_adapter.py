import json
import subprocess
import sys

import pytest

from app.core.models import EvaluationCase
from app.systems.pdf_signer.adapter import PDFSignerAdapter


def _case(input_data: dict) -> EvaluationCase:
    return EvaluationCase(id="pdf-1", system="pdf_signer", input=input_data)


def test_explicit_python_executable_overrides_environment(monkeypatch):
    monkeypatch.setenv("PDF_SIGNER_PYTHON", "/env/python")

    adapter = PDFSignerAdapter(python_executable="/explicit/python")

    assert adapter.python_executable == "/explicit/python"


def test_python_environment_variable_is_used_without_constructor_argument(
    monkeypatch,
):
    monkeypatch.setenv("PDF_SIGNER_PYTHON", "/env/python")

    adapter = PDFSignerAdapter()

    assert adapter.python_executable == "/env/python"


def test_sys_executable_is_the_python_fallback(monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)

    adapter = PDFSignerAdapter()

    assert adapter.python_executable == sys.executable


def test_detect_builds_command_and_parses_json(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)
    backend = tmp_path / "pdf_backend.py"
    backend.write_text("", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='[{"x": 12, "y": 24, "w": 100, "h": 50}]',
        stderr="",
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed

    monkeypatch.setattr("app.systems.pdf_signer.adapter.subprocess.run", fake_run)

    result = PDFSignerAdapter(backend).run(
        _case({"operation": "detect", "pdf_path": "input.pdf", "page_number": 2})
    )

    assert calls[0][0] == [
        sys.executable,
        str(backend),
        "detect",
        "input.pdf",
        "2",
    ]
    assert calls[0][1] == {
        "capture_output": True,
        "text": True,
        "check": False,
    }
    assert result.output["areas"] == json.loads(completed.stdout)
    assert result.output["page_number"] == 2


def test_detect_ignores_noisy_stdout_before_json(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)
    backend = tmp_path / "pdf_backend.py"
    backend.write_text("", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            "unexpected backend warning\n"
            '[{"x": 180.0, "y": 452.17, "w": 122.31, "h": 36.0}]\n'
        ),
        stderr="",
    )
    monkeypatch.setattr(
        "app.systems.pdf_signer.adapter.subprocess.run",
        lambda *args, **kwargs: completed,
    )

    result = PDFSignerAdapter(backend).run(
        _case({"operation": "detect", "pdf_path": "input.pdf", "page_number": 0})
    )

    assert result.output["areas"] == [
        {"x": 180.0, "y": 452.17, "w": 122.31, "h": 36.0}
    ]


def test_detect_without_json_raises_runtime_error(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)
    backend = tmp_path / "pdf_backend.py"
    backend.write_text("", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="warning only\nnot JSON", stderr=""
    )
    monkeypatch.setattr(
        "app.systems.pdf_signer.adapter.subprocess.run",
        lambda *args, **kwargs: completed,
    )

    with pytest.raises(RuntimeError, match="returned invalid JSON"):
        PDFSignerAdapter(backend).run(
            _case({"operation": "detect", "pdf_path": "input.pdf", "page_number": 0})
        )


def test_place_builds_command_and_parses_output_path(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)
    backend = tmp_path / "pdf_backend.py"
    backend.write_text("", encoding="utf-8")
    output_path = tmp_path / "signed.pdf"
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=f"  {output_path}\n", stderr=""
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return completed

    monkeypatch.setattr("app.systems.pdf_signer.adapter.subprocess.run", fake_run)

    result = PDFSignerAdapter(backend).run(
        _case(
            {
                "operation": "place",
                "pdf_path": "input.pdf",
                "page_number": 1,
                "x": 10,
                "y": 20,
                "signature_image_path": "signature.png",
                "width": 180,
                "height": 70,
                "output_path": str(output_path),
            }
        )
    )

    assert calls[0][-2:] == ["--output", str(output_path)]
    assert result.output["output_path"] == str(output_path)
    assert result.output["width"] == 180
    assert result.output["height"] == 70


def test_place_uses_final_non_empty_stdout_line(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)
    backend = tmp_path / "pdf_backend.py"
    backend.write_text("", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="unexpected backend warning\n\n/tmp/signed.pdf\n",
        stderr="",
    )
    monkeypatch.setattr(
        "app.systems.pdf_signer.adapter.subprocess.run",
        lambda *args, **kwargs: completed,
    )

    result = PDFSignerAdapter(backend).run(
        _case(
            {
                "operation": "place",
                "pdf_path": "input.pdf",
                "page_number": 1,
                "x": 10,
                "y": 20,
                "signature_image_path": "signature.png",
            }
        )
    )

    assert result.output["output_path"] == "/tmp/signed.pdf"


def test_missing_backend_configuration_is_rejected(monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)

    with pytest.raises(ValueError, match="backend is not configured"):
        PDFSignerAdapter().run(
            _case({"pdf_path": "input.pdf", "page_number": 1})
        )


def test_subprocess_failure_raises_concise_runtime_error(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_SIGNER_PYTHON", raising=False)
    monkeypatch.delenv("PDF_SIGNER_BACKEND_PATH", raising=False)
    backend = tmp_path / "pdf_backend.py"
    backend.write_text("", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=[], returncode=2, stdout="", stderr="bad PDF"
    )
    monkeypatch.setattr(
        "app.systems.pdf_signer.adapter.subprocess.run",
        lambda *args, **kwargs: completed,
    )

    with pytest.raises(RuntimeError, match="exit code 2: bad PDF"):
        PDFSignerAdapter(backend).run(
            _case({"pdf_path": "input.pdf", "page_number": 1})
        )