"""Application-level adapter and evaluator registration."""

from app.core.registry import Registry, registry as default_registry
from app.systems.ata_rag import ATARagAdapter, default_evaluators
from app.systems.ata_rag.usage_evaluators import usage_evaluators
from app.systems.internship import (
    CoordinatorDecisionEvaluator,
    CoordinatorEvidenceEvaluator,
    CoordinatorLatencyThreshold,
    CoordinatorNotesQualityEvaluator,
    CoordinatorSchemaEvaluator,
    InternshipCoordinatorAdapter,
)
from app.systems.pdf_signer import (
    PDFOutputEvaluator,
    PDFSignerAdapter,
    SignatureCoordinateEvaluator,
    SignatureDetectionEvaluator,
)
from app.systems.report_reviewer import (
    ReportDecisionEvaluator,
    ReportFindingEvaluator,
    ReportReviewerAdapter,
    ReportSchemaEvaluator,
)


def register_default_integrations(registry: Registry = default_registry) -> Registry:
    """Register local adapters/evaluators without validating external services."""
    adapters = {
        "ata-rag": ATARagAdapter(),
        "internship-coordinator": InternshipCoordinatorAdapter(),
        "report-reviewer": ReportReviewerAdapter(),
        "pdf-signer": PDFSignerAdapter(),
    }
    for system, adapter in adapters.items():
        if system not in registry.list_systems():
            registry.register_adapter(system, adapter)

    evaluators = [
        *default_evaluators(),
        *usage_evaluators(),
        CoordinatorDecisionEvaluator(),
        CoordinatorEvidenceEvaluator(),
        CoordinatorLatencyThreshold(),
        CoordinatorNotesQualityEvaluator(),
        CoordinatorSchemaEvaluator(),
        ReportDecisionEvaluator(),
        ReportFindingEvaluator(),
        ReportSchemaEvaluator(),
        PDFOutputEvaluator(),
        SignatureCoordinateEvaluator(),
        SignatureDetectionEvaluator(),
    ]
    for evaluator in evaluators:
        if evaluator.name not in registry.list_evaluators():
            registry.register_evaluator(evaluator.name, evaluator)
    return registry