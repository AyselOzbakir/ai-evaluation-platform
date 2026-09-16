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
