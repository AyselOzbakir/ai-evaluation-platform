"""FastAPI app entrypoint. Person 1 registers real adapters/evaluators here once the relevant PRs merge."""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="AI Evaluation Platform")
app.include_router(router)

# Real adapters/evaluators are registered here as each system's module lands, e.g.:
#   from app.systems.ata_rag.adapter import ATARagAdapter
#   from app.core.registry import registry
#   registry.register_adapter("ata-rag", ATARagAdapter())
