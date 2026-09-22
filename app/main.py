"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.bootstrap import register_default_integrations
from app.reporting.routes import router as reporting_router

app = FastAPI(title="AI Evaluation Platform")
register_default_integrations()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)
app.include_router(reporting_router)
