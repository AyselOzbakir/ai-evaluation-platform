import json

import pytest

from app.core.datasets import DatasetError, load_dataset


def _case(case_id: str) -> dict:
    return {"id": case_id, "system": "fake", "input": {"q": "hi"}}


def test_load_json_array(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("c1"), _case("c2")]), encoding="utf-8")
    cases = load_dataset(path)
    assert [c.id for c in cases] == ["c1", "c2"]


def test_load_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(_case(cid)) for cid in ["c1", "c2"]), encoding="utf-8")
    cases = load_dataset(path)
    assert [c.id for c in cases] == ["c1", "c2"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(DatasetError):
        load_dataset(tmp_path / "missing.json")


def test_empty_array_raises(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(path)


def test_invalid_case_raises(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"id": "c1"}]), encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(path)


def test_duplicate_id_raises(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("c1"), _case("c1")]), encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(path)


def test_top_level_must_be_array(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(_case("c1")), encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(path)
