"""Optional Langfuse client facade with lazy imports and fail-open behavior."""

from __future__ import annotations

import os
from typing import Any

from app.integrations.langfuse.metadata import trace_url


class DisabledLangfuseClient:
    enabled = False
    trace_id = None
    observation_id = None

    def start_trace(self, name: str, metadata: dict[str, Any], input_data: Any = None):
        return self

    def start_observation(self, name: str, metadata: dict[str, Any], input_data: Any = None):
        return self

    def update(self, **kwargs: Any) -> None:
        return None

    def score(self, **kwargs: Any) -> None:
        return None

    def end(self) -> None:
        return None

    def flush(self) -> None:
        return None


class LangfuseClient:
    """Small facade around the current Langfuse Python SDK."""

    def __init__(self, sdk_client: Any, project_id: str, base_url: str) -> None:
        self._sdk_client = sdk_client
        self.project_id = project_id
        self.base_url = base_url
        self.enabled = True
        self.trace_id: str | None = None
        self.observation_id: str | None = None

    def start_trace(
        self,
        name: str,
        metadata: dict[str, Any],
        input_data: Any = None,
    ) -> "LangfuseClient":
        observation = self._sdk_client.start_observation(
            name=name,
            input=input_data,
            metadata=metadata,
        )
        return _ObservationHandle(self, observation)

    def start_observation(
        self,
        name: str,
        metadata: dict[str, Any],
        input_data: Any = None,
    ) -> "LangfuseClient":
        observation = self._sdk_client.start_observation(
            name=name,
            input=input_data,
            metadata=metadata,
        )
        return _ObservationHandle(self, observation)

    def flush(self) -> None:
        self._sdk_client.flush()


class _ObservationHandle:
    def __init__(self, root: LangfuseClient, observation: Any) -> None:
        self._root = root
        self._observation = observation
        self.enabled = True
        self.trace_id = getattr(observation, "trace_id", None)
        self.observation_id = getattr(observation, "id", None)
        if root.trace_id is None:
            root.trace_id = self.trace_id
        if root.observation_id is None:
            root.observation_id = self.observation_id

    def start_trace(self, name: str, metadata: dict[str, Any], input_data: Any = None):
        return self._root.start_observation(name, metadata, input_data)

    def start_observation(self, name: str, metadata: dict[str, Any], input_data: Any = None):
        return self._root.start_observation(name, metadata, input_data)

    def update(self, **kwargs: Any) -> None:
        self._observation.update(**kwargs)

    def score(self, **kwargs: Any) -> None:
        self._observation.score(**kwargs)

    def end(self) -> None:
        self._observation.end()

    def flush(self) -> None:
        self._root.flush()


def create_client(
    sdk_client: Any | None = None,
    environ: dict[str, str] | None = None,
) -> DisabledLangfuseClient | LangfuseClient:
    env = environ if environ is not None else os.environ
    public_key = env.get("LANGFUSE_PUBLIC_KEY")
    secret_key = env.get("LANGFUSE_SECRET_KEY")
    project_id = env.get("LANGFUSE_PROJECT_ID")
    base_url = env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST")
    if not public_key or not secret_key or not project_id or not base_url:
        return DisabledLangfuseClient()
    if sdk_client is not None:
        return LangfuseClient(sdk_client, project_id, base_url.rstrip("/"))

    try:
        from langfuse import Langfuse

        sdk = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
        )
        return LangfuseClient(sdk, project_id, base_url.rstrip("/"))
    except Exception:
        return DisabledLangfuseClient()


def safe_trace_url(client: Any) -> str | None:
    return trace_url(
        getattr(client, "base_url", None),
        getattr(client, "project_id", None),
        getattr(client, "trace_id", None),
    )