import pytest

from app.core.registry import Registry, RegistryError
from tests.core.fakes import FakeAdapter, FakeEvaluator


def test_register_and_get_adapter():
    reg = Registry()
    adapter = FakeAdapter()
    reg.register_adapter("fake", adapter)
    assert reg.get_adapter("fake") is adapter
    assert reg.list_systems() == ["fake"]


def test_register_and_get_evaluator():
    reg = Registry()
    evaluator = FakeEvaluator()
    reg.register_evaluator(evaluator.name, evaluator)
    assert reg.get_evaluator("fake_exact_match") is evaluator
    assert reg.list_evaluators() == ["fake_exact_match"]


def test_missing_adapter_raises():
    reg = Registry()
    with pytest.raises(RegistryError):
        reg.get_adapter("does-not-exist")


def test_missing_evaluator_raises():
    reg = Registry()
    with pytest.raises(RegistryError):
        reg.get_evaluator("does-not-exist")
