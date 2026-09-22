"""Optional synchronization of local evaluation datasets to Langfuse."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.core.datasets import load_dataset
from app.core.models import EvaluationCase
from app.integrations.langfuse.client import create_client

SAFE_METADATA_KEYS = {
    "dataset_version",
    "system",
    "split",
    "category",
    "synthetic",
}


@dataclass(frozen=True)
class DatasetPublishResult:
    dataset_name: str
    dataset_version: str
    created_items: int
    skipped_items: int


def dataset_name_for_system(system: str, prefix: str | None = None) -> str:
    configured_prefix = prefix
    if configured_prefix is None:
        configured_prefix = os.environ.get("LANGFUSE_DATASET_PREFIX", "")
    return f"{configured_prefix.rstrip('-') + '-' if configured_prefix else ''}{system}"


def publish_dataset(
    dataset_name: str,
    cases: Sequence[EvaluationCase],
    client: Any,
    *,
    dataset_version: str | None = None,
) -> DatasetPublishResult:
    if not getattr(client, "enabled", False):
        raise RuntimeError("Langfuse is unavailable or not configured.")
    if not cases:
        raise ValueError("Cannot publish an empty dataset.")

    version = dataset_version or _dataset_version(cases)
    try:
        client.create_dataset(
            name=dataset_name,
            metadata={"dataset_version": version, "system": cases[0].system},
        )
    except Exception as exc:
        if not _is_duplicate_error(exc):
            raise
    created = 0
    skipped = 0
    for case in cases:
        item_metadata = {
            key: value
            for key, value in case.metadata.items()
            if key in SAFE_METADATA_KEYS
        }
        item_metadata.update(
            {"case_id": case.id, "dataset_version": version, "system": case.system}
        )
        try:
            client.create_dataset_item(
                dataset_name=dataset_name,
                id=case.id,
                input=case.input,
                expected_output=case.expected_output,
                metadata=item_metadata,
            )
            created += 1
        except Exception as exc:
            if _is_duplicate_error(exc):
                skipped += 1
                continue
            raise
    client.flush()
    return DatasetPublishResult(dataset_name, version, created, skipped)


def _dataset_version(cases: Sequence[EvaluationCase]) -> str:
    versions = {case.metadata.get("dataset_version") for case in cases}
    versions.discard(None)
    if len(versions) != 1:
        raise ValueError("Dataset cases must contain one consistent dataset_version.")
    return next(iter(versions))


def _is_duplicate_error(error: Exception) -> bool:
    message = str(error).lower()
    return "already exists" in message or "duplicate" in message or "conflict" in message


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a local dataset to Langfuse.")
    parser.add_argument("--system", required=True)
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--dataset-name")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    client = create_client()
    if not getattr(client, "enabled", False):
        raise SystemExit("Langfuse is unavailable: configure SDK and credentials first.")
    cases = [case for case in load_dataset(args.dataset_path) if case.system == args.system]
    if not cases:
        raise SystemExit(f"No cases for system {args.system!r} found in dataset.")
    name = args.dataset_name or dataset_name_for_system(args.system)
    result = publish_dataset(
        name,
        cases,
        client,
        dataset_version=args.dataset_version,
    )
    print(json.dumps(result.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())