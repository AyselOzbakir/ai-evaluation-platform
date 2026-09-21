"""ATA-local factory for the generic LLM-as-a-Judge evaluator."""

from pathlib import Path

from app.evaluators.llm_judge.client import JudgeClient
from app.evaluators.llm_judge.evaluator import LLMJudgeEvaluator
from app.evaluators.llm_judge.rubric import load_rubric

RUBRIC_PATH = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "ata_rag"
    / "rubrics.yaml"
)
RUBRIC_NAMES = (
    "answer_correctness",
    "groundedness",
    "citation_source_correctness",
)


def default_judge_evaluators(
    judge_client: JudgeClient,
    model_name: str | None = None,
    provider: str | None = None,
    rubric_path: str | Path = RUBRIC_PATH,
) -> list[LLMJudgeEvaluator]:
    return [
        LLMJudgeEvaluator(
            rubric=load_rubric(rubric_path, name=name),
            judge_client=judge_client,
            model_name=model_name,
            provider=provider,
        )
        for name in RUBRIC_NAMES
    ]