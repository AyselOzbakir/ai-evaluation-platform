"""Deterministic evaluator tests using hand-built SystemOutput objects."""

from app.core.models import EvaluationCase, SystemOutput
from app.systems.ata_rag import (
    LatencyThreshold,
    NoAnswerBehavior,
    OutputSchemaValidation,
    RetrievalPrecisionAtK,
    RetrievalRecallAtK,
    default_evaluators,
)

A = "https://akademiata.pl/a"
B = "https://akademiata.pl/b"
C = "https://akademiata.pl/c"


def case(sources=None, no_answer=False, category="factual"):
    expected = {"answer": "x"}
    if sources is not None:
        expected["sources"] = sources
    if no_answer:
        expected = {"no_answer": True}
    return EvaluationCase(
        id="c1", system="ata-rag", input={"question": "q"},
        expected_output=expected, metadata={"category": category},
    )


def out(sources, no_answer=False, answer="An answer.", latency=1000, client=None):
    return SystemOutput(
        output={"answer": answer, "sources": sources, "no_answer": no_answer},
        metadata={"latency_ms": latency, "client_latency_ms": client},
    )


# --- recall ---------------------------------------------------------------


def test_recall_full_hit():
    r = RetrievalRecallAtK().evaluate(case([A]), out([B, A]))
    assert r.evaluator == "retrieval_recall_at_k"
    assert r.score == 1.0 and r.passed


def test_recall_partial_miss_fails_default_threshold():
    r = RetrievalRecallAtK().evaluate(case([A, B]), out([A, C]))
    assert r.score == 0.5 and not r.passed


def test_recall_respects_k_cutoff():
    r = RetrievalRecallAtK(k=1).evaluate(case([A]), out([B, A]))
    assert r.score == 0.0 and not r.passed


def test_recall_compares_normalized_urls():
    r = RetrievalRecallAtK().evaluate(case(["https://AkademiaTA.pl/a/"]), out([A]))
    assert r.score == 1.0


def test_recall_skipped_without_expected_sources():
    r = RetrievalRecallAtK().evaluate(case(None), out([A]))
    assert r.score is None and r.passed and r.metadata["skipped"]


# --- precision ------------------------------------------------------------


def test_precision_counts_relevant_share():
    r = RetrievalPrecisionAtK().evaluate(case([A]), out([A, B, C, "https://x/d"]))
    assert r.score == 0.25 and r.passed


def test_precision_no_sources_returned_fails():
    r = RetrievalPrecisionAtK().evaluate(case([A]), out([]))
    assert r.score == 0.0 and not r.passed


def test_precision_below_threshold_fails():
    r = RetrievalPrecisionAtK(min_precision=0.5).evaluate(case([A]), out([A, B, C]))
    assert not r.passed


def test_precision_skipped_without_expected_sources():
    r = RetrievalPrecisionAtK().evaluate(case(None), out([A]))
    assert r.passed and r.metadata["skipped"]


# --- no-answer behaviour --------------------------------------------------


def test_no_answer_expected_and_declined_passes():
    r = NoAnswerBehavior().evaluate(case(no_answer=True, category="no_answer"), out([], no_answer=True))
    assert r.passed


def test_no_answer_expected_but_answered_fails():
    r = NoAnswerBehavior().evaluate(case(no_answer=True, category="no_answer"), out([A]))
    assert not r.passed


def test_no_answer_inferred_from_category():
    c = EvaluationCase(id="c", system="ata-rag", input={"question": "q"}, metadata={"category": "no_answer"})
    assert NoAnswerBehavior().evaluate(c, out([], no_answer=True)).passed


def test_answerable_question_declined_fails():
    r = NoAnswerBehavior().evaluate(case([A]), out([], no_answer=True))
    assert not r.passed and "declined" in r.reason


def test_answerable_question_without_sources_fails():
    r = NoAnswerBehavior().evaluate(case([A]), out([]))
    assert not r.passed


def test_answerable_question_with_sources_passes():
    assert NoAnswerBehavior().evaluate(case([A]), out([B])).passed


# --- latency --------------------------------------------------------------


def test_latency_within_limit():
    r = LatencyThreshold(max_ms=2000).evaluate(case([A]), out([A], latency=1500))
    assert r.passed and r.metadata["latency_source"] == "latency_ms"


def test_latency_over_limit():
    assert not LatencyThreshold(max_ms=1000).evaluate(case([A]), out([A], latency=1500)).passed


def test_latency_falls_back_to_client_measurement():
    r = LatencyThreshold().evaluate(case([A]), out([A], latency=None, client=500))
    assert r.passed and r.metadata["latency_source"] == "client_latency_ms"


def test_latency_missing_fails():
    assert not LatencyThreshold().evaluate(case([A]), out([A], latency=None)).passed


# --- schema ---------------------------------------------------------------


def test_schema_valid_output():
    assert OutputSchemaValidation().evaluate(case([A]), out([A])).passed


def test_schema_invalid_output_lists_problems():
    bad = SystemOutput(output={"answer": "", "sources": "nope"})
    r = OutputSchemaValidation().evaluate(case([A]), bad)
    assert not r.passed
    assert "answer" in r.reason and "sources" in r.reason and "no_answer" in r.reason


def test_default_evaluator_names_are_unique_and_stable():
    names = [e.name for e in default_evaluators()]
    assert names == [
        "output_schema_validation",
        "retrieval_recall_at_k",
        "retrieval_precision_at_k",
        "no_answer_behavior",
        "latency_threshold",
    ]
