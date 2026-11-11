"""Unit tests for `TaskTrackerClientFactory` (POL-4)."""

from typing import Any

import pytest

from trackerkit.contracts.auth import GitHubAuthConfig, JiraAuthConfig, ProviderAuthConfig
from trackerkit.domain.enums import Provider
from trackerkit.domain.errors import ConfigurationError
from trackerkit.factory.client_factory import TaskTrackerClientFactory


class _FakeProviderAuthConfig(ProviderAuthConfig):
    provider: Any = "fake"
    api_key: str


class _FakeClient:
    def __init__(self, config: _FakeProviderAuthConfig, relation_mapping: Any = None) -> None:
        self.config = config
        self.relation_mapping = relation_mapping


def test_built_in_providers_are_pre_registered() -> None:
    config = GitHubAuthConfig(access_token="x")
    client = TaskTrackerClientFactory.create(config)
    assert client.__class__.__name__ == "GitHubClient"


def test_create_rejects_config_with_wrong_type() -> None:
    misfit = JiraAuthConfig(
        provider=Provider.GITHUB,  # type: ignore[arg-type]
        base_url="https://x",
        access_token="x",
    )
    with pytest.raises(ConfigurationError):
        TaskTrackerClientFactory.create(misfit)


def test_register_adds_custom_provider_and_unregister_removes_it() -> None:
    try:
        TaskTrackerClientFactory.register("fake", _FakeProviderAuthConfig, _FakeClient)
        config = _FakeProviderAuthConfig(api_key="abc")
        client = TaskTrackerClientFactory.create(config)
        assert isinstance(client, _FakeClient)
        assert client.config is config
    finally:
        TaskTrackerClientFactory.unregister("fake")


def test_unsupported_provider_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        TaskTrackerClientFactory.build_auth_config("unknown", {})


def test_build_auth_config_for_built_in_provider() -> None:
    config = TaskTrackerClientFactory.build_auth_config(Provider.GITHUB, {"access_token": "x"})
    assert isinstance(config, GitHubAuthConfig)


def test_removed_asana_provider_is_not_registered() -> None:
    with pytest.raises(ValueError):
        Provider("asana")
