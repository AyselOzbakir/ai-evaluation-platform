# ATA RAG evaluation module (Person 2)

Connects the existing [ATA RAG](https://github.com/Mehmetsdk/ATA-Rag) backend to the
evaluation platform. It only *calls* ATA (`POST /api/chat`); no RAG logic is copied here.

## Files

| Path | What |
|---|---|
| `app/systems/ata_rag/adapter.py` | `ATARagAdapter` (normalizes ATA's response into `SystemOutput`) |
| `app/systems/ata_rag/evaluators.py` | Deterministic evaluators + `default_evaluators()` |
| `app/systems/ata_rag/dataset.py` | Dataset validator / category counts |
| `configs/ata_rag/rubrics.yaml` | LLM-judge rubrics (answer correctness, groundedness, citation correctness) |
| `datasets/ata_rag/` | Golden dataset `ata-rag-v1` (JSON array of `EvaluationCase`) |
| `tests/ata_rag/` | Tests (mocked ATA, no API keys needed) |

## Case input fields

```json
{"question": "required string", "language": "en | pl (default en)", "history": [ /* optional chat messages */ ]}
```

## Adapter output

`SystemOutput.output`:

- `answer` (str)
- `sources` (list of normalized source page URLs, lowercase without trailing `/`, in ATA order)
- `no_answer` (bool, true when ATA returned its "couldn't find enough verified information" message)

`SystemOutput.metadata`: `latency_ms` (measured by ATA), `client_latency_ms` (measured by the
adapter), `confidence`, `query_id`, `source_details` (title/url/section/excerpt/source_type per source).

Configuration: `ATA_RAG_BASE_URL` (or `ATARagAdapter(base_url=...)`), timeout defaults to 30 s.
Failures (unreachable, timeout, HTTP error, invalid JSON, unexpected shape) raise `ATARagError`
with a readable message; the core runner records it as a failed case.

## Dataset format (`datasets/ata_rag/ata-rag-v1.json`)

```json
{
  "id": "ata-001",
  "system": "ata-rag",
  "input": {"question": "...", "language": "en"},
  "expected_output": {"answer": "key facts", "sources": ["https://akademiata.pl/..."]},
  "metadata": {"category": "factual", "difficulty": "easy"}
}
```

Categories: `factual`, `multi_document`, `ambiguous`, `no_answer`, `misleading_assumption`,
`source_attribution`. For `no_answer` cases use `"expected_output": {"no_answer": true}`.
Expected sources must be real page URLs from ATA's knowledge base. Check a dataset file with:

```
python -m app.systems.ata_rag.dataset datasets/ata_rag/ata-rag-v1.json
```

## Evaluators

`output_schema_validation`, `retrieval_recall_at_k`, `retrieval_precision_at_k`
(both k=5, ATA's default top-k), `no_answer_behavior`, `latency_threshold` (10 s default).
Thresholds are constructor arguments. Recall/precision are skipped (`passed=True`,
`metadata.skipped=True`, `score=None`) for cases without expected sources.

## Running

```
uv run pytest tests/ata_rag
```

Real run: start ATA (or use a deployed instance), set `ATA_RAG_BASE_URL`, register
`ATARagAdapter` and `default_evaluators()` through the core registry (Person 1).

## Known limitations

- ATA's `sources` are the retrieved pages (top 5, de-duplicated by URL), not necessarily the
  pages the answer relied on. "Citation" checks are therefore retrieval checks at page level;
  chunk-level retrieval metrics are not possible from the current API output.
- ATA returns the same no-answer message when its OpenAI key is missing or the LLM call fails,
  so a no-answer result alone cannot prove the backend is healthy. Answerable cases in the
  dataset act as the health check.
- `confidence` is the best chunk's similarity score, not a correctness estimate.
