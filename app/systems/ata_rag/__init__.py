"""ATA RAG evaluation module (Person 2)."""

from app.systems.ata_rag.adapter import ATARagAdapter, ATARagError, normalize_url
from app.systems.ata_rag.evaluators import (
    LatencyThreshold,
    NoAnswerBehavior,
    OutputSchemaValidation,
    RetrievalPrecisionAtK,
    RetrievalRecallAtK,
    default_evaluators,
)

__all__ = [
    "ATARagAdapter",
    "ATARagError",
    "normalize_url",
    "LatencyThreshold",
    "NoAnswerBehavior",
    "OutputSchemaValidation",
    "RetrievalPrecisionAtK",
    "RetrievalRecallAtK",
    "default_evaluators",
]
