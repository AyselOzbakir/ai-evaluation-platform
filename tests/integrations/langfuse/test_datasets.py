import pytest

from app.core.models import EvaluationCase
from app.integrations.langfuse.datasets import (
    dataset_name_for_system,
    publish_dataset,
)


def cases():
    return [
        EvaluationCase(
            id="case-001",
            system="synthetic",
            input={"question": "q"},
            expected_output={"answer": "a"},
            metadata={
                "dataset_version": "synthetic-v1",
                "synthetic": True,
                "split": "golden",
                "category": "test",
                "secret": "never-publish",
            },
        ),
        EvaluationCase(
            id="case-002",
            system="synthetic",
            input={"question": "q2"},
            expected_output={"answer": "a2"},
            metadata={"dataset_version": "synthetic-v1", "synthetic": True},
        ),
    ]


class FakeLangfuse:
    enabled = True

    def __init__(self):
        self.datasets = []
        self.items = []
        self.runs = []
        self.flush_count = 0

    def create_dataset(self, **kwargs):
        self.datasets.append(kwargs)

    def create_dataset_item(self, **kwargs):
        if any(item["id"] == kwargs["id"] for item in self.items):
            raise RuntimeError("duplicate item")
        self.items.append({"id": kwargs["id"], **kwargs})

    def start_dataset_run(self, **kwargs):
        self.runs.append(kwargs)
        return {"run": kwargs["run_name"]}

    def flush(self):
        self.flush_count += 1


def test_publish_dataset_preserves_ids_and_safe_metadata():
    client = FakeLangfuse()

    result = publish_dataset("synthetic-v1", cases(), client)

    assert result.created_items == 2
    assert result.skipped_items == 0
    assert [item["id"] for item in client.items] == ["case-001", "case-002"]
    assert client.items[0]["metadata"]["dataset_version"] == "synthetic-v1"
    assert "secret" not in client.items[0]["metadata"]
    assert client.flush_count == 1


def test_publish_dataset_is_duplicate_safe():
    client = FakeLangfuse()

    first = publish_dataset("synthetic-v1", cases(), client)
    second = publish_dataset("synthetic-v1", cases(), client)

    assert first.created_items == 2
    assert second.created_items == 0
    assert second.skipped_items == 2
    assert len(client.items) == 2


def test_disabled_client_fails_clearly_and_name_is_stable():
    with pytest.raises(RuntimeError, match="unavailable"):
        publish_dataset("synthetic-v1", cases(), type("Disabled", (), {"enabled": False})())
    assert dataset_name_for_system("ata-rag", "golden") == "golden-ata-rag"

