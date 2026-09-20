"""Deterministic ATA RAG evaluators. All return the shared ``EvaluationResult``.

Dataset conventions (see README):
- ``expected_output["sources"]``: list of expected source page URLs.
- ``expected_output["no_answer"]``: ``True`` for questions ATA should refuse
  (also inferred from ``metadata["category"] == "no_answer"``).

Source URLs are compared after ``normalize_url`` (lowercase, no trailing '/').
"""

from __future__ import annotations

from app.core.models import EvaluationCase, EvaluationResult, Evaluator, SystemOutput
from app.systems.ata_rag.adapter import normalize_url

DEFAULT_TOP_K = 5  # ATA's default RETRIEVAL_TOP_K


def _expected_sources(case: EvaluationCase) -> list[str]:
    return [normalize_url(u) for u in (case.expected_output.get("sources") or [])]


def _actual_sources(output: SystemOutput) -> list[str]:
    return [normalize_url(u) for u in (output.output.get("sources") or [])]


def _expects_no_answer(case: EvaluationCase) -> bool:
    return bool(case.expected_output.get("no_answer")) or case.metadata.get("category") == "no_answer"


def _skipped(name: str, reason: str) -> EvaluationResult:
    return EvaluationResult(
        evaluator=name, score=None, passed=True, reason=reason, metadata={"skipped": True}
    )


class RetrievalRecallAtK(Evaluator):
    """Share of the expected source URLs found among the first ``k`` returned sources."""

    name = "retrieval_recall_at_k"

    def __init__(self, k: int = DEFAULT_TOP_K, min_recall: float = 1.0) -> None:
        self.k = k
        self.min_recall = min_recall

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        expected = _expected_sources(case)
        if not expected:
            return _skipped(self.name, "No expected sources for this case; skipped.")
        top_k = _actual_sources(output)[: self.k]
        found = [u for u in expected if u in top_k]
        recall = len(found) / len(expected)
        return EvaluationResult(
            evaluator=self.name,
            score=recall,
            passed=recall >= self.min_recall,
            reason=f"Found {len(found)}/{len(expected)} expected sources in top {self.k}.",
            metadata={"k": self.k, "expected": expected, "retrieved_top_k": top_k, "found": found},
        )


class RetrievalPrecisionAtK(Evaluator):
    """Share of the first ``k`` returned sources that are expected sources.

    Note: with a single expected source and 5 returned sources the best
    possible precision is 0.2, so ``min_precision`` defaults to 0.2.
    """

    name = "retrieval_precision_at_k"

    def __init__(self, k: int = DEFAULT_TOP_K, min_precision: float = 0.2) -> None:
        self.k = k
        self.min_precision = min_precision

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        expected = _expected_sources(case)
        if not expected:
            return _skipped(self.name, "No expected sources for this case; skipped.")
        top_k = _actual_sources(output)[: self.k]
        if not top_k:
            return EvaluationResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                reason="No sources returned.",
                metadata={"k": self.k, "expected": expected, "retrieved_top_k": []},
            )
        relevant = [u for u in top_k if u in expected]
        precision = len(relevant) / len(top_k)
        return EvaluationResult(
            evaluator=self.name,
            score=precision,
            passed=precision >= self.min_precision,
            reason=f"{len(relevant)}/{len(top_k)} returned sources are expected sources.",
            metadata={"k": self.k, "expected": expected, "retrieved_top_k": top_k},
        )


class NoAnswerBehavior(Evaluator):
    """Checks refusal behaviour and that answerable questions come with sources.

    - Expected no-answer: ATA must return its no-answer message and no sources.
    - Expected answerable: ATA must not refuse and must return at least one source.
    """

    name = "no_answer_behavior"

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        no_answer = bool(output.output.get("no_answer"))
        sources = _actual_sources(output)
        if _expects_no_answer(case):
            ok = no_answer and not sources
            reason = (
                "Correctly declined to answer."
                if ok
                else "Expected a no-answer response with no sources, but ATA answered."
            )
        else:
            ok = (not no_answer) and bool(sources)
            if ok:
                reason = "Answered and returned at least one source."
            elif no_answer:
                reason = "ATA declined to answer an answerable question."
            else:
                reason = "ATA answered without returning any source."
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if ok else 0.0,
            passed=ok,
            reason=reason,
            metadata={"expected_no_answer": _expects_no_answer(case), "returned_sources": len(sources)},
        )


class LatencyThreshold(Evaluator):
    """Passes when latency (ATA-reported, else client-measured) is within ``max_ms``."""

    name = "latency_threshold"

    def __init__(self, max_ms: int = 10_000) -> None:
        self.max_ms = max_ms

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        latency = output.metadata.get("latency_ms")
        source = "latency_ms"
        if latency is None:
            latency = output.metadata.get("client_latency_ms")
            source = "client_latency_ms"
        if latency is None:
            return EvaluationResult(
                evaluator=self.name, score=0.0, passed=False, reason="No latency information in output."
            )
        ok = latency <= self.max_ms
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if ok else 0.0,
            passed=ok,
            reason=f"Latency {latency} ms vs limit {self.max_ms} ms.",
            metadata={"latency_ms": latency, "max_ms": self.max_ms, "latency_source": source},
        )


class OutputSchemaValidation(Evaluator):
    """Checks the normalized output has the fields the other evaluators rely on."""

    name = "output_schema_validation"

    def evaluate(self, case: EvaluationCase, output: SystemOutput) -> EvaluationResult:
        problems: list[str] = []
        answer = output.output.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            problems.append("'answer' must be a non-empty string")
        sources = output.output.get("sources")
        if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
            problems.append("'sources' must be a list of URL strings")
        if not isinstance(output.output.get("no_answer"), bool):
            problems.append("'no_answer' must be a boolean")
        ok = not problems
        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if ok else 0.0,
            passed=ok,
            reason="Output schema is valid." if ok else "; ".join(problems),
        )


def default_evaluators() -> list[Evaluator]:
    """The standard deterministic ATA evaluator set (used for registration by Person 1)."""
    return [
        OutputSchemaValidation(),
        RetrievalRecallAtK(),
        RetrievalPrecisionAtK(),
        NoAnswerBehavior(),
        LatencyThreshold(),
    ]
