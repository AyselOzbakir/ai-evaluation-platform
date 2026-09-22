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
artifacts/observability/  generated Langfuse sidecars (gitignored)
artifacts/human_evaluations/  local human-review fallback JSON (gitignored)
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

## Runtime Registration and Execution

The application bootstraps these adapters and deterministic evaluators from `app/bootstrap.py`:
`ata-rag`, `internship-coordinator`, `report-reviewer`, and `pdf-signer`. Registration is local
only and does not contact external services. `POST /evaluations/run` uses the application service,
which calls the optional Langfuse-aware runner and then persists the normal JSON experiment artifact.

To add a new system, implement `SystemAdapter` / `Evaluator` in `app/systems/<name>/` or
`app/evaluators/<name>/`, then add its local bootstrap registration without changing the shared core.

## API

`GET /health`, `GET /systems`, `POST /evaluations/run`, `GET /evaluations/{id}`,
`GET /experiments`, `GET /experiments/{id}`.

### Human Evaluations

Submit an additive human review for an existing experiment case:

```bash
curl -X POST http://127.0.0.1:8000/human-evaluations \
  -H 'Content-Type: application/json' \
  -d '{
    "experiment_id": "<experiment-id>",
    "case_id": "<case-id>",
    "evaluator_name": "reviewer",
    "score": 0.85,
    "passed": true,
    "label": "approved",
    "comment": "Reviewed by a human evaluator."
  }'
```

Read reviews with `GET /human-evaluations/{experiment_id}`. Human reviews are retained
separately from deterministic and LLM evaluator results. Without `DATABASE_URL`, local JSON
fallback storage is used under `artifacts/human_evaluations/`.

## PostgreSQL Persistence

PostgreSQL persistence is optional. Configure a SQLAlchemy-compatible PostgreSQL URL:

```bash
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/ai_evaluation"
```

When configured, experiment results and human evaluations are written to PostgreSQL in addition
to the existing JSON artifacts. The application still starts without `DATABASE_URL`; no database
connection is created during startup. Initialize the schema explicitly with:

```bash
DATABASE_URL="$DATABASE_URL" python3 -c \
  'from app.persistence.database import create_repository; create_repository()'
```

The schema contains `experiments` and `human_evaluations` tables. SQLite is used only in unit tests
for repository behavior; production PostgreSQL remains the supported database backend.

## Langfuse Datasets

The Langfuse integration can publish local golden datasets while preserving each case's stable ID:

```bash
python -m app.integrations.langfuse.datasets \
  --system ata-rag \
  --dataset-path datasets/ata_rag/ata-rag-v1.json \
  --dataset-version ata-rag-v1
```

Set `LANGFUSE_DATASET_PREFIX` to control the hosted dataset name, for example
`golden` produces `golden-ata-rag`. The publisher uses `id=<case id>` for Langfuse dataset items,
so rerunning the command is duplicate-safe/upsert-oriented. It publishes only safe dataset
metadata such as system, version, split, category, and synthetic status.

When `LANGFUSE_DATASET_PREFIX` is configured and Langfuse is enabled, evaluation runs fetch the
matching hosted dataset and call the Langfuse v4 `dataset.run_experiment(...)` API. The task
reconstructs each local `EvaluationCase`, executes the registered adapter/evaluators once, and
returns the captured result to Langfuse. The resulting `dataset_run_id` and `dataset_run_url` are
stored in the local experiment metadata and observability sidecar. If the dataset is unavailable,
the SDK is missing, or credentials fail, execution falls back to the normal local runner.

Langfuse remains optional. Without the SDK or credentials, normal local evaluation and JSON
artifacts continue to work; dataset publishing exits clearly with a configuration error.

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

ATA token and cost measurements are supported when the external ATA response exposes usage
fields. The adapter normalizes input/output/total tokens, model name, and backend-provided cost;
missing values remain unavailable rather than being estimated. Optional local pricing can be
configured with `ATA_MODEL_PRICING_PATH` using explicit USD-per-million-token rates. Unknown
models and missing usage never receive fabricated values.

## Dashboard

Start the application and open [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard).
The lightweight static HTML/JavaScript dashboard uses the existing FastAPI endpoints to provide:

- Experiment history sorted by start time, with system, dataset, application version, and status.
- Baseline and candidate experiment selectors.
- Overall `PASS`/`FAIL` comparison results.
- Metric baseline, candidate, delta, and improved/regressed/unchanged status.
- Regression `Gate` and `Reason` details for each metric.
- Newly failing cases and resolved cases.
- Optional Langfuse trace and hosted dataset experiment links.

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

Langfuse trace and hosted dataset-run links are shown when safe observability sidecars contain
those URLs; the dashboard remains functional when Langfuse is disabled.

## External Runtime Prerequisites

- ATA RAG: set `ATA_RAG_BASE_URL` and run the external ATA service.
- Internship Coordinator: set `INTERNSHIP_COORDINATOR_PATH` and optionally
  `INTERNSHIP_COORDINATOR_PYTHON`.
- Report Reviewer: set `REPORT_REVIEWER_PATH` and optionally `REPORT_REVIEWER_PYTHON`.
- PDF Signer: set `PDF_SIGNER_BACKEND_PATH` and optionally `PDF_SIGNER_PYTHON`.
- Langfuse: configure its `LANGFUSE_*` variables and install dependencies with `uv sync`.

External services are never contacted during application startup; they are used only when an
evaluation runs.

## Testing

Run the full test suite with:

```bash
python3 -m pytest -q
```

Run `python3 -m pytest -q -rs` to verify the current suite.

## Experiment Metadata

Run configuration accepts optional `model_version`, `model_name`, `prompt_version`,
`config_version`, `evaluator_versions`, and `metadata` fields. These values are persisted in the
experiment artifact when supplied and safe version/evaluator fields are propagated to Langfuse.
Existing requests that omit them remain valid.

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
