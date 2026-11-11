from typing import ClassVar

from trackerkit.contracts.auth import (
    GitHubAuthConfig,
    JiraAuthConfig,
    ProviderAuthConfig,
    YandexTrackerAuthConfig,
)
from trackerkit.contracts.task_tracker_client import TaskTrackerClient
from trackerkit.domain.enums import Provider
from trackerkit.domain.errors import ConfigurationError
from trackerkit.domain.relation_mapping import RelationMappingConfig
from trackerkit.providers.github.client import GitHubClient
from trackerkit.providers.jira.client import JiraClient
from trackerkit.providers.yandex_tracker.client import YandexTrackerClient


class TaskTrackerClientFactory:
    """Factory for provider-specific clients with a pluggable registry.

    Built-in providers (`Provider.JIRA`, `Provider.YANDEX_TRACKER`,
    `Provider.GITHUB`) are registered at import time. Host applications may
    register additional providers via :meth:`register` to plug in custom
    adapters without editing the library.
    """

    _config_registry: ClassVar[dict[Provider | str, type[ProviderAuthConfig]]] = {}
    _client_registry: ClassVar[dict[Provider | str, type[TaskTrackerClient]]] = {}

    @classmethod
    def register(
        cls,
        provider: Provider | str,
        config_cls: type[ProviderAuthConfig],
        client_cls: type[TaskTrackerClient],
    ) -> None:
        """Register a provider with its auth-config and client classes.

        Re-registering an existing provider replaces the previous entry. Use a
        string key for providers that are not part of the built-in
        :class:`Provider` enum.
        """
        key = cls._normalize_key(provider)
        cls._config_registry[key] = config_cls
        cls._client_registry[key] = client_cls

    @classmethod
    def unregister(cls, provider: Provider | str) -> None:
        key = cls._normalize_key(provider)
        cls._config_registry.pop(key, None)
        cls._client_registry.pop(key, None)

    @staticmethod
    def _normalize_key(provider: Provider | str) -> Provider | str:
        if isinstance(provider, Provider):
            return provider
        try:
            return Provider(provider)
        except ValueError:
            return provider

    @classmethod
    def create(
        cls,
        config: ProviderAuthConfig,
        relation_mapping: RelationMappingConfig | None = None,
    ) -> TaskTrackerClient:
        key = cls._normalize_key(config.provider)
        config_type = cls._config_registry.get(key)
        client_type = cls._client_registry.get(key)

        if config_type is None or client_type is None:
            raise ConfigurationError(f"Unsupported provider: {config.provider}")

        if not isinstance(config, config_type):
            raise ConfigurationError(
                f"Expected {config_type.__name__} for provider "
                f"{getattr(config.provider, 'value', config.provider)}."
            )

        if relation_mapping is None:
            return client_type(config)
        return client_type(config, relation_mapping=relation_mapping)

    @classmethod
    def build_auth_config(cls, provider: Provider | str, auth_data: dict) -> ProviderAuthConfig:
        key = cls._normalize_key(provider)
        config_type = cls._config_registry.get(key)

        if config_type is None:
            raise ConfigurationError(f"Unsupported provider: {provider}")

        return config_type(**auth_data)


# Built-in providers — registered at import time. Host code may extend the
# registry via `TaskTrackerClientFactory.register(...)`.
TaskTrackerClientFactory.register(Provider.JIRA, JiraAuthConfig, JiraClient)
TaskTrackerClientFactory.register(
    Provider.YANDEX_TRACKER, YandexTrackerAuthConfig, YandexTrackerClient
)
TaskTrackerClientFactory.register(Provider.GITHUB, GitHubAuthConfig, GitHubClient)
