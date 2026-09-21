"""Optional SQLAlchemy persistence layer.

No engine or connection is created until ``create_repository`` is called.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import JSON

from app.core.experiment import ExperimentResult


class Base(DeclarativeBase):
    pass


class ExperimentRecord(Base):
    __tablename__ = "experiments"

    experiment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    system: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(255), nullable=False)
    application_version: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    aggregate_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class HumanEvaluationRecord(Base):
    __tablename__ = "human_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DatabaseRepository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def save_experiment(self, experiment: ExperimentResult) -> None:
        with Session(self.engine) as session:
            existing = session.get(ExperimentRecord, experiment.experiment_id)
            if existing is not None:
                raise ValueError(f"Experiment already exists in database: {experiment.experiment_id}")
            data = experiment.model_dump(mode="json")
            session.add(
                ExperimentRecord(
                    experiment_id=experiment.experiment_id,
                    system=experiment.system,
                    dataset_version=experiment.dataset_version,
                    application_version=experiment.application_version,
                    started_at=experiment.started_at,
                    passed=experiment.passed,
                    aggregate_metrics=experiment.aggregate_metrics,
                    metadata_json=experiment.metadata,
                    raw_result=data,
                )
            )
            session.commit()

    def add_human_evaluation(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        with Session(self.engine) as session:
            record = HumanEvaluationRecord(
                experiment_id=evaluation["experiment_id"],
                case_id=evaluation["case_id"],
                evaluator_name=evaluation["evaluator_name"],
                score=evaluation.get("score"),
                passed=evaluation.get("passed"),
                label=evaluation.get("label"),
                comment=evaluation.get("comment"),
                created_at=evaluation["created_at"],
                metadata_json=evaluation.get("metadata", {}),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return human_evaluation_dict(record)

    def list_human_evaluations(self, experiment_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            records = session.scalars(
                select(HumanEvaluationRecord)
                .where(HumanEvaluationRecord.experiment_id == experiment_id)
                .order_by(HumanEvaluationRecord.id)
            ).all()
            return [human_evaluation_dict(record) for record in records]


def create_repository(database_url: str | None = None) -> DatabaseRepository | None:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        return None
    repository = DatabaseRepository(url)
    repository.initialize()
    return repository


def human_evaluation_dict(record: HumanEvaluationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "experiment_id": record.experiment_id,
        "case_id": record.case_id,
        "evaluator_name": record.evaluator_name,
        "score": record.score,
        "passed": record.passed,
        "label": record.label,
        "comment": record.comment,
        "created_at": record.created_at.isoformat(),
        "metadata": record.metadata_json,
    }