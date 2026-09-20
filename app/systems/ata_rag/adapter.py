"""Adapter that connects the existing ATA RAG backend to the evaluation core.

The adapter only *calls* the running ATA RAG backend (``POST /api/chat``) and
normalizes its response into the shared ``SystemOutput`` shape. No RAG logic
lives here.

Real ATA response (backend/app/schemas.py, ChatResponse)::

    {"answer": str, "sources": [{"title", "url", "section", "excerpt",
     "source_type"}], "confidence": float | null, "latency_ms": int | null,
     "query_id": str}

Things worth knowing when interpreting the output:
- ``sources`` are the URLs of the top retrieved chunks (default top_k=5, min
  score 0.35), de-duplicated by URL. They are NOT necessarily what the LLM used
  to write the answer.
- When ATA cannot answer it returns a fixed "I couldn't find enough verified
  information ..." message with an empty source list. ATA returns the same
  message if its OpenAI key is missing or the LLM call fails, so a no-answer
  result cannot be told apart from a broken backend on its own.
- ``confidence`` is the similarity score of the best chunk, not a correctness
  estimate.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from app.core.models import EvaluationCase, SystemAdapter, SystemOutput

NO_ANSWER_PREFIX = "I couldn't find enough verified information"
DEFAULT_TIMEOUT_S = 30.0
CHAT_PATH = "/api/chat"

# (url, json payload, timeout seconds) -> parsed JSON dict
HttpPost = Callable[[str, dict[str, Any], float], dict[str, Any]]


class ATARagError(RuntimeError):
    """Readable, controlled error for anything that goes wrong calling ATA RAG.

    The core runner is expected to capture this as a failed case result.
    """


def normalize_url(url: str) -> str:
    """Normalize a URL the same way ATA de-duplicates sources (trim, no trailing '/', lowercase)."""
    return url.strip().rstrip("/").lower()


def _default_http_post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ATARagError(f"ATA RAG returned HTTP {exc.code} for {url}") from exc
    except TimeoutError as exc:
        raise ATARagError(f"ATA RAG timed out after {timeout}s ({url})") from exc
    except urllib.error.URLError as exc:
        raise ATARagError(f"Could not reach ATA RAG at {url}: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ATARagError("ATA RAG returned a response that is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ATARagError("ATA RAG returned JSON that is not an object")
    return parsed


class ATARagAdapter(SystemAdapter):
    """Runs an ``EvaluationCase`` against a running ATA RAG backend.

    Case input fields: ``question`` (required), ``language`` (``"en"`` or
    ``"pl"``, default ``"en"``), ``history`` (optional list of chat messages).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        http_post: HttpPost | None = None,
    ) -> None:
        self._base_url = base_url
        self.timeout = timeout
        self._post = http_post or _default_http_post

    @property
    def base_url(self) -> str:
        base = self._base_url or os.environ.get("ATA_RAG_BASE_URL")
        if not base:
            raise ATARagError(
                "ATA RAG base URL is not set. Pass base_url or set ATA_RAG_BASE_URL."
            )
        return base.rstrip("/")

    def run(self, case: EvaluationCase) -> SystemOutput:
        question = case.input.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ATARagError(f"Case {case.id}: input must contain a non-empty 'question'")

        payload: dict[str, Any] = {
            "question": question,
            "language": case.input.get("language", "en"),
        }
        history = case.input.get("history")
        if history:
            payload["history"] = history

        started = time.perf_counter()
        raw = self._post(self.base_url + CHAT_PATH, payload, self.timeout)
        client_latency_ms = int((time.perf_counter() - started) * 1000)
        return self.normalize_response(raw, client_latency_ms=client_latency_ms)

    @staticmethod
    def normalize_response(raw: dict[str, Any], client_latency_ms: int | None = None) -> SystemOutput:
        """Turn a raw ATA ``ChatResponse`` dict into the shared ``SystemOutput``."""
        answer = raw.get("answer")
        if not isinstance(answer, str):
            raise ATARagError("ATA RAG response has no 'answer' string")
        raw_sources = raw.get("sources")
        if not isinstance(raw_sources, list):
            raise ATARagError("ATA RAG response has no 'sources' list")

        source_urls: list[str] = []
        source_details: list[dict[str, Any]] = []
        for item in raw_sources:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            normalized = normalize_url(item["url"])
            if normalized in source_urls:
                continue
            source_urls.append(normalized)
            source_details.append(
                {
                    "url": item["url"],
                    "title": item.get("title"),
                    "section": item.get("section"),
                    "excerpt": item.get("excerpt"),
                    "source_type": item.get("source_type"),
                }
            )

        return SystemOutput(
            output={
                "answer": answer,
                "sources": source_urls,
                "no_answer": answer.strip().startswith(NO_ANSWER_PREFIX),
            },
            metadata={
                "latency_ms": raw.get("latency_ms"),
                "client_latency_ms": client_latency_ms,
                "confidence": raw.get("confidence"),
                "query_id": raw.get("query_id"),
                "source_details": source_details,
            },
        )
