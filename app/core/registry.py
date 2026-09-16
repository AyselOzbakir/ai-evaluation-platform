"""Registry for adapters and evaluators, keyed by a stable string name."""

from app.core.models import Evaluator, SystemAdapter


class RegistryError(KeyError):
    pass


class Registry:
    def __init__(self) -> None:
        self._adapters: dict[str, SystemAdapter] = {}
        self._evaluators: dict[str, Evaluator] = {}

    def register_adapter(self, system: str, adapter: SystemAdapter) -> None:
        self._adapters[system] = adapter

    def register_evaluator(self, name: str, evaluator: Evaluator) -> None:
        self._evaluators[name] = evaluator

    def get_adapter(self, system: str) -> SystemAdapter:
        try:
            return self._adapters[system]
        except KeyError:
            raise RegistryError(f"No adapter registered for system {system!r}") from None

    def get_evaluator(self, name: str) -> Evaluator:
        try:
            return self._evaluators[name]
        except KeyError:
            raise RegistryError(f"No evaluator registered with name {name!r}") from None

    def list_systems(self) -> list[str]:
        return sorted(self._adapters)

    def list_evaluators(self) -> list[str]:
        return sorted(self._evaluators)


registry = Registry()
