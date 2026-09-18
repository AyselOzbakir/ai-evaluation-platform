# AI Evaluation Platform

Reusable evaluation engine for the team's AI systems (ATA RAG, Internship Coordinator, Internship
Report Reviewer, PDF Signer). One core engine; each system plugs in through a small adapter.

Team working agreement, folder ownership and per-person AI prompts: see
`AI_Evaluation_Team_Guide_21Sep_Updated.pdf` (shared separately, not in this repo). Full product
requirements: `AI Evaluation Platform Project Requirements.pdf`.

## Setup

```bash
uv sync
uv run pytest              # Person 1's tests only need this repo, no API keys
uv run uvicorn app.main:app --reload
```

## Architecture

```
app/core/        Person 1 - shared models, registry, runner, config, storage, hooks, API routes
app/systems/      one adapter package per AI system (Person 2, 3, 5)
app/evaluators/   Person 4 - generic LLM-as-a-judge
app/integrations/ Person 4 - Langfuse
app/experiments/  Person 5 - comparison/regression logic
app/reporting/    Person 5 - dashboard data
app/templates/    Person 5 - Jinja2 pages
datasets/         one JSON dataset per system
artifacts/experiments/  generated experiment result JSON (gitignored)
configs/          YAML run configs (see configs/example.yaml)
```

## Shared contract (frozen - do not rename without agreement from all five people)

`app/core/models.py`:

- `EvaluationCase(id, system, input, expected_output, metadata)`
- `SystemOutput(output, metadata)`
- `EvaluationResult(evaluator, score, passed, reason, metadata)`
- `SystemAdapter.run(case) -> SystemOutput`
- `Evaluator.evaluate(case, output) -> EvaluationResult`

`app/core/experiment.py` defines the on-disk experiment JSON shape (`ExperimentResult`,
`CaseResult`) that Person 5's dashboard reads.

## How to plug in a new adapter or evaluator

1. Implement `SystemAdapter` / `Evaluator` in your own `app/systems/<name>/` or
   `app/evaluators/<name>/` package. Do not edit `app/core/**`.
2. Register it (in `app/main.py`, near the existing commented-out examples):
   ```python
   from app.core.registry import registry
   from app.systems.ata_rag.adapter import ATARagAdapter
   registry.register_adapter("ata-rag", ATARagAdapter())
   ```
3. Point a YAML config at it (see `configs/example.yaml`) and either call
   `app.core.runner.run_experiment(config, registry)` directly, or `POST /evaluations/run` with the
   config as the JSON body.
4. Until your real system is ready, write your own tests against the frozen interfaces using a fake
   adapter/evaluator (see `tests/core/fakes.py` for the pattern) - never block on another person's
   branch.

## API

`GET /health`, `GET /systems`, `POST /evaluations/run`, `GET /evaluations/{id}`,
`GET /experiments`, `GET /experiments/{id}`.

## Experiment Reporting

Person 5's comparison layer compares a baseline experiment with a candidate experiment. It reports
metrics as improved, regressed, or unchanged, identifies newly failing cases and resolved cases,
and applies configurable regression gates.

Regression rules are defined in `configs/regression_rules.yaml` and loaded by the reporting layer:

```yaml
metrics:
  correctness_avg_score:
    direction: higher
    minimum: 0.90
    max_regression: 0.02
  case_error_rate:
    direction: lower
    maximum: 0.05
    max_regression: 0.02
```

- `direction` is `higher` for metrics where larger values are better, or `lower` where smaller
  values are better.
- `minimum` and `maximum` define candidate value bounds when applicable.
- `max_regression` limits the allowed movement in the unfavorable direction from baseline.

## Dashboard

Start the application and open [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard).
The lightweight static HTML/JavaScript dashboard uses the existing FastAPI endpoints to provide:

- Experiment history sorted by start time, with system, dataset, application version, and status.
- Baseline and candidate experiment selectors.
- Overall `PASS`/`FAIL` comparison results.
- Metric baseline, candidate, delta, and improved/regressed/unchanged status.
- Regression `Gate` and `Reason` details for each metric.
- Newly failing cases and resolved cases.

## Orange PDF Signer Integration

The reusable adapter is in `app/systems/pdf_signer/`. The external Orange PDF Signer repository is
not copied into this repository. Instead, the adapter invokes its `pdf_backend.py` CLI through
`subprocess`.

Supported operations are `detect` and `place`. Configure the external backend with:

```bash
export PDF_SIGNER_BACKEND_PATH="/path/to/orange-pdf-signer/pdf_backend.py"
export PDF_SIGNER_PYTHON="/path/to/orange-pdf-signer/.venv/bin/python"
```

`PDF_SIGNER_PYTHON` is optional. It is useful when the external signer needs its own Python
environment for dependencies such as PyMuPDF and Pillow. The adapter also provides deterministic
evaluators for signature detection, coordinate matching, and generated PDF output:

- `SignatureDetectionEvaluator`
- `SignatureCoordinateEvaluator`
- `PDFOutputEvaluator`

Dashboard trace links can be connected once the Langfuse integration exposes its trace URL or
metadata contract. Langfuse dashboard links are not currently assumed by this reporting layer.

## Testing

Run the full test suite with:

```bash
python3 -m pytest -q
```

At the time of this implementation, the full suite passes with 49 tests.

## Experiment JSON shape

```json
{
  "experiment_id": "2026-09-20_ata-rag_baseline",
  "system": "ata-rag",
  "dataset_version": "ata-rag-v1",
  "application_version": "git-sha-or-label",
  "started_at": "2026-09-20T10:00:00+00:00",
  "case_results": [
    {"case_id": "ata-001", "output": {...}, "evaluations": [...], "error": null}
  ],
  "aggregate_metrics": {"answer_correctness_avg_score": 0.91},
  "passed": true
}
```
