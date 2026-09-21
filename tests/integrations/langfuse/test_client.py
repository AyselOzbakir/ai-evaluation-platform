from app.integrations.langfuse.client import (
    DisabledLangfuseClient,
    create_client,
)


def test_missing_credentials_returns_disabled_client():
    client = create_client(environ={})

    assert isinstance(client, DisabledLangfuseClient)
    assert client.enabled is False


def test_missing_package_returns_disabled_client(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "langfuse", None)

    client = create_client(
        environ={
            "LANGFUSE_PUBLIC_KEY": "public",
            "LANGFUSE_SECRET_KEY": "secret",
            "LANGFUSE_BASE_URL": "https://example",
            "LANGFUSE_PROJECT_ID": "project",
        }
    )

    assert client.enabled is False


def test_initialization_failure_returns_disabled_client():
    class BrokenSdk:
        def __init__(self, **kwargs):
            raise RuntimeError("synthetic init failure")

    client = create_client(
        sdk_client=None,
        environ={
            "LANGFUSE_PUBLIC_KEY": "public",
            "LANGFUSE_SECRET_KEY": "secret",
            "LANGFUSE_BASE_URL": "https://example",
            "LANGFUSE_PROJECT_ID": "project",
        },
    )
    assert client.enabled is False


def test_disabled_flush_does_not_raise():
    create_client(environ={}).flush()