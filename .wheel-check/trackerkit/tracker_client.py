import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from trackerkit.contracts.task_tracker_client import TaskTrackerClient
from trackerkit.domain.enums import ConnectionErrorKind, Provider
from trackerkit.domain.errors import AuthenticationError, ConfigurationError, ProviderError
from trackerkit.domain.models import (
    Comment,
    ConnectionDiagnostic,
    CreateCommentInput,
    CreateProjectInput,
    CreateRelationInput,
    CreateTaskInput,
    Project,
    Relation,
    Task,
    TaskQuery,
    UpdateProjectInput,
    UpdateRelationInput,
    UpdateTaskInput,
    User,
    Workspace,
)
from trackerkit.domain.relation_mapping import RelationMappingConfig
from trackerkit.factory.client_factory import TaskTrackerClientFactory

T = TypeVar("T")
logger = logging.getLogger("trackerkit.tracker_client")


class TrackerClient:
    """Facade over provider-specific clients.

    One instance of this class works with one selected task tracker only.
    """

    def __init__(
        self,
        provider: Provider | str,
        auth_data: dict,
        connection_timeout: float = 3.0,
        max_retries: int = 0,
        relation_mapping: RelationMappingConfig | None = None,
        connection_check_ttl: float = 30.0,
        verify_each_call: bool = False,
    ) -> None:
        """Create a facade client for one selected provider.

        `auth_data` is provider-specific:
        - `jira`: `base_url` and exactly one of `access_token` or `api_token`
        - `yandex_tracker`: exactly one of `token` or `iam_token`, and exactly
          one of `org_id` or `cloud_org_id`
        - `github`: `access_token`; optional `base_url`, `api_version`, and
          `max_concurrency`

        Connection check semantics:
        - by default, the first business call triggers one provider auth check
          and the result is cached for ``connection_check_ttl`` seconds, so
          subsequent calls do not pay the round-trip cost;
        - ``verify_each_call=True`` forces a fresh check before every call;
        - ``invalidate_connection_cache()`` lets callers reset the cache after
          out-of-band token rotation.
        """

        if connection_timeout <= 0:
            raise ConfigurationError("connection_timeout must be a positive number of seconds.")
        if max_retries < 0:
            raise ConfigurationError("max_retries must be zero or positive.")
        if connection_check_ttl < 0:
            raise ConfigurationError(
                "connection_check_ttl must be zero or positive (0 disables caching)."
            )

        self._provider = Provider(provider)
        config_data = {
            **auth_data,
            "timeout_seconds": connection_timeout,
            "max_retries": max_retries,
        }

        self._auth_config = TaskTrackerClientFactory.build_auth_config(
            self._provider,
            config_data,
        )
        self._client: TaskTrackerClient = TaskTrackerClientFactory.create(
            self._auth_config,
            relation_mapping=relation_mapping,
        )
        self._connection_check_ttl = float(connection_check_ttl)
        self._verify_each_call = bool(verify_each_call)
        self._last_successful_check_at: float | None = None

    @property
    def provider(self) -> Provider:
        return self._provider

    def _build_connection_error(
        self,
        diagnostic: ConnectionDiagnostic,
    ) -> AuthenticationError | ConfigurationError | ProviderError:
        message = (
            diagnostic.message or f"Provider '{self._provider.value}' connection check failed."
        )

        if diagnostic.error_kind is ConnectionErrorKind.AUTHENTICATION:
            return AuthenticationError(message)

        if diagnostic.error_kind is ConnectionErrorKind.CONFIGURATION:
            return ConfigurationError(message)

        return ProviderError(message)

    def _connection_cache_is_fresh(self) -> bool:
        if self._verify_each_call:
            return False
        if self._last_successful_check_at is None:
            return False
        if self._connection_check_ttl <= 0:
            return False
        return time.monotonic() - self._last_successful_check_at < self._connection_check_ttl

    def invalidate_connection_cache(self) -> None:
        """Drop the cached successful connection check.

        Useful after out-of-band auth changes (e.g. token rotation) to force
        the next call to re-verify.
        """
        self._last_successful_check_at = None

    async def _ensure_connection(self) -> None:
        if self._connection_cache_is_fresh():
            return
        diagnostic = await self.get_connection_diagnostic()
        if not diagnostic.is_connected:
            self._last_successful_check_at = None
            logger.warning(
                "Provider connection check failed: provider=%s kind=%s type=%s message=%s",
                self._provider.value,
                diagnostic.error_kind.value if diagnostic.error_kind else "unknown",
                diagnostic.error_type or "unknown",
                diagnostic.message or "no details",
            )
            raise self._build_connection_error(diagnostic)
        self._last_successful_check_at = time.monotonic()

    async def _execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        await self._ensure_connection()
        return await operation()

    async def check_connection(self) -> bool:
        diagnostic = await self.get_connection_diagnostic()
        return diagnostic.is_connected

    async def ensure_connection(self) -> None:
        await self._ensure_connection()

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        return await self._client.get_connection_diagnostic()

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> "TrackerClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def get_task(self, task_id: str) -> Task:
        return await self._execute(lambda: self._client.get_task(task_id))

    async def list_tasks(self, query: TaskQuery | None = None) -> list[Task]:
        return await self._execute(lambda: self._client.list_tasks(query))

    async def count_tasks(self, query: TaskQuery | None = None) -> int:
        return await self._execute(lambda: self._client.count_tasks(query))

    async def create_task(self, payload: CreateTaskInput) -> Task:
        return await self._execute(lambda: self._client.create_task(payload))

    async def update_task(self, task_id: str, payload: UpdateTaskInput) -> Task:
        return await self._execute(lambda: self._client.update_task(task_id, payload))

    async def delete_task(self, task_id: str) -> None:
        await self._execute(lambda: self._client.delete_task(task_id))

    async def list_workspaces(self) -> list[Workspace]:
        return await self._execute(self._client.list_workspaces)

    async def get_project(self, project_id: str) -> Project:
        return await self._execute(lambda: self._client.get_project(project_id))

    async def list_projects(self, workspace_id: str | None = None) -> list[Project]:
        return await self._execute(lambda: self._client.list_projects(workspace_id))

    async def create_project(self, payload: CreateProjectInput) -> Project:
        return await self._execute(lambda: self._client.create_project(payload))

    async def update_project(
        self,
        project_id: str,
        payload: UpdateProjectInput,
    ) -> Project:
        return await self._execute(lambda: self._client.update_project(project_id, payload))

    async def delete_project(self, project_id: str) -> None:
        await self._execute(lambda: self._client.delete_project(project_id))

    async def list_users(self) -> list[User]:
        return await self._execute(self._client.list_users)

    async def list_comments(self, task_id: str) -> list[Comment]:
        return await self._execute(lambda: self._client.list_comments(task_id))

    async def create_comment(self, payload: CreateCommentInput) -> Comment:
        return await self._execute(lambda: self._client.create_comment(payload))

    async def list_relations(self, task_id: str) -> list[Relation]:
        return await self._execute(lambda: self._client.list_relations(task_id))

    async def create_relation(self, payload: CreateRelationInput) -> Relation:
        return await self._execute(lambda: self._client.create_relation(payload))

    async def update_relation(
        self,
        relation_id: str,
        payload: UpdateRelationInput,
    ) -> Relation:
        return await self._execute(lambda: self._client.update_relation(relation_id, payload))

    async def delete_relation(self, relation_id: str) -> None:
        await self._execute(lambda: self._client.delete_relation(relation_id))
