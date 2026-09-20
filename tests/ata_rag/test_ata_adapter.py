"""Adapter tests. No real ATA RAG, network or API key is needed."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.core.models import EvaluationCase
from app.systems.ata_rag import ATARagAdapter, ATARagError, normalize_url

NO_ANSWER_TEXT = (
    "I couldn't find enough verified information in the indexed university sources "
    "to answer this question."
)

RAW_OK = {
    "answer": "Computer Science tuition is 1000 PLN per month.",
    "sources": [
        {
            "title": "Tuition",
            "url": "https://akademiata.pl/kalkulator-czesnego/",
            "section": "Fees",
            "excerpt": "Tuition ...",
            "source_type": "website",
        },
        {"title": "Admissions", "url": "https://akademiata.pl/admissions", "source_type": "website"},
    ],
    "confidence": 0.84,
    "latency_ms": 1430,
    "query_id": "abc-123",
}


def make_case(**input_overrides):
    data = {"question": "How much is Computer Science tuition?", "language": "en"}
    data.update(input_overrides)
    return EvaluationCase(id="ata-001", system="ata-rag", input=data)


def fake_post(response, calls=None):
    def post(url, payload, timeout):
        if calls is not None:
            calls.append((url, payload, timeout))
        return response

    return post


def test_normalize_url_matches_ata_deduplication():
    assert normalize_url(" https://AkademiaTA.pl/Admissions/ ") == "https://akademiata.pl/admissions"


def test_run_normalizes_response_into_system_output():
    calls = []
    adapter = ATARagAdapter(base_url="http://ata.test/", http_post=fake_post(RAW_OK, calls))

    result = adapter.run(make_case())

    assert result.output == {
        "answer": RAW_OK["answer"],
        "sources": ["https://akademiata.pl/kalkulator-czesnego", "https://akademiata.pl/admissions"],
        "no_answer": False,
    }
    assert result.metadata["latency_ms"] == 1430
    assert result.metadata["confidence"] == 0.84
    assert result.metadata["query_id"] == "abc-123"
    assert isinstance(result.metadata["client_latency_ms"], int)
    assert result.metadata["source_details"][0]["title"] == "Tuition"
    assert result.metadata["source_details"][0]["url"] == "https://akademiata.pl/kalkulator-czesnego/"
    # Request goes to the /api/chat route with question + language.
    url, payload, timeout = calls[0]
    assert url == "http://ata.test/api/chat"
    assert payload == {"question": "How much is Computer Science tuition?", "language": "en"}
    assert timeout == 30.0


def test_history_is_forwarded_when_present():
    calls = []
    adapter = ATARagAdapter(base_url="http://ata.test", http_post=fake_post(RAW_OK, calls))
    history = [{"role": "user", "content": "Hi"}]

    adapter.run(make_case(history=history, language="pl"))

    assert calls[0][1]["history"] == history
    assert calls[0][1]["language"] == "pl"


def test_no_answer_response_is_flagged():
    raw = {"answer": NO_ANSWER_TEXT, "sources": [], "confidence": None, "latency_ms": 900, "query_id": "q"}
    result = ATARagAdapter.normalize_response(raw)

    assert result.output["no_answer"] is True
    assert result.output["sources"] == []
    assert result.metadata["confidence"] is None


def test_duplicate_source_urls_are_collapsed():
    raw = {
        "answer": "x",
        "sources": [{"url": "https://akademiata.pl/a/"}, {"url": "https://AKADEMIATA.pl/a"}],
        "query_id": "q",
    }
    result = ATARagAdapter.normalize_response(raw)
    assert result.output["sources"] == ["https://akademiata.pl/a"]
    assert len(result.metadata["source_details"]) == 1


@pytest.mark.parametrize("raw", [{"sources": []}, {"answer": "x"}, {"answer": 5, "sources": []}])
def test_malformed_response_raises_readable_error(raw):
    with pytest.raises(ATARagError):
        ATARagAdapter.normalize_response(raw)


def test_missing_question_raises():
    adapter = ATARagAdapter(base_url="http://ata.test", http_post=fake_post(RAW_OK))
    case = EvaluationCase(id="x", system="ata-rag", input={})
    with pytest.raises(ATARagError, match="question"):
        adapter.run(case)


def test_missing_base_url_raises(monkeypatch):
    monkeypatch.delenv("ATA_RAG_BASE_URL", raising=False)
    adapter = ATARagAdapter(http_post=fake_post(RAW_OK))
    with pytest.raises(ATARagError, match="ATA_RAG_BASE_URL"):
        adapter.run(make_case())


def test_base_url_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("ATA_RAG_BASE_URL", "http://from-env.test")
    calls = []
    ATARagAdapter(http_post=fake_post(RAW_OK, calls)).run(make_case())
    assert calls[0][0] == "http://from-env.test/api/chat"


# --- real HTTP path against a tiny local server (no external network) ---------


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        if self.path == "/api/chat" and body["question"] == "boom":
            self.send_response(500)
            self.end_headers()
            return
        if self.path == "/api/chat" and body["question"] == "garbage":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not json")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(RAW_OK).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def local_ata():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_real_http_success(local_ata):
    result = ATARagAdapter(base_url=local_ata).run(make_case())
    assert result.output["answer"] == RAW_OK["answer"]


def test_real_http_server_error(local_ata):
    with pytest.raises(ATARagError, match="HTTP 500"):
        ATARagAdapter(base_url=local_ata).run(make_case(question="boom"))


def test_real_http_invalid_json(local_ata):
    with pytest.raises(ATARagError, match="not valid JSON"):
        ATARagAdapter(base_url=local_ata).run(make_case(question="garbage"))


def test_unreachable_server_raises_readable_error():
    adapter = ATARagAdapter(base_url="http://127.0.0.1:1", timeout=2)
    with pytest.raises(ATARagError, match="Could not reach|timed out"):
        adapter.run(make_case())
