import asyncio
import logging
from typing import Any

from yandex_tracker_client import TrackerClient as YandexSDKClient
from yandex_tracker_client.collections import Links

from trackerkit.contracts.auth import YandexTrackerAuthConfig
from trackerkit.domain.enums import Provider
from trackerkit.domain.errors import get_error_kind
from trackerkit.domain.models import ConnectionDiagnostic
from trackerkit.providers.yandex_tracker.errors import raise_yandex_error


class YandexTrackerTransport:
    def __init__(self, config: YandexTrackerAuthConfig) -> None:
        self._config = config
        self._client: YandexSDKClient | None = None

    def _get_client(self) -> YandexSDKClient:
        if self._client is None:
            self._client = YandexSDKClient(
                token=self._config.token,
                iam_token=self._config.iam_token,
                org_id=self._config.org_id,
                cloud_org_id=self._config.cloud_org_id,
                timeout=self._config.timeout_seconds,
            )
        return self._client

    async def _run(self, func, /, *args, **kwargs):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as error:
            raise_yandex_error(error)

    async def _run_quietly(self, func, /, *args, **kwargs):
        logger = logging.getLogger("yandex_tracker_client.connection")
        previous_disabled = logger.disabled
        logger.disabled = True
        try:
            return await self._run(func, *args, **kwargs)
        finally:
            logger.disabled = previous_disabled

    async def check_connection(self) -> bool:
        diagnostic = await self.get_connection_diagnostic()
        return diagnostic.is_connected

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        try:
            await self._run_quietly(lambda: self._get_client().myself)
        except Exception as error:
            return ConnectionDiagnostic(
                provider=Provider.YANDEX_TRACKER,
                is_connected=False,
                error_kind=get_error_kind(error),
                message=str(error),
                error_type=type(error).__name__,
            )
        return ConnectionDiagnostic(
            provider=Provider.YANDEX_TRACKER,
            is_connected=True,
        )

    async def get_issue(self, task_id: str) -> Any:
        return await self._run(self._get_client().issues.get, task_id)

    async def find_issues(self, query: str | None, per_page: int, **kwargs) -> list[Any]:
        # ``issues.find`` returns a lazy ``PaginatedList``: it has no ``__len__``
        # and performs blocking HTTP requests while iterated to follow ``next``
        # links. Materialize it into a real list inside the worker thread so the
        # paging I/O stays off the event loop and callers get a plain ``list``.
        def _materialize() -> list[Any]:
            return list(self._get_client().issues.find(query, per_page, **kwargs))

        return await self._run(_materialize)

    async def count_issues(self, query: str | None, **kwargs) -> int:
        # Uses Tracker's dedicated ``/issues/_count`` endpoint (a single cheap
        # request that returns just the number), instead of paging the issues.
        def _count() -> int:
            return int(
                self._get_client().issues.find(query, count_only=True, **kwargs)
            )

        return await self._run(_count)

    async def create_issue(self, data: dict[str, Any]) -> Any:
        return await self._run(self._get_client().issues.create, **data)

    async def update_issue(self, issue: Any, data: dict[str, Any]) -> None:
        await self._run(issue.update, **data)

    async def delete_issue(self, issue: Any) -> None:
        await self._run(issue.delete)

    async def get_issue_links(self, issue: Any) -> list[Any]:
        return await self._run(issue.links.get_all)

    async def create_issue_link(
        self,
        source_issue: Any,
        relationship: str,
        target_task_id: str,
    ) -> Any:
        return await self._run(source_issue.links.create, relationship, target_task_id)

    def _links_collection(self) -> Links:
        return Links(self._get_client()._connection)

    async def get_link(self, relation_id: str) -> Any:
        return await self._run(self._links_collection().get, relation_id)

    async def delete_link(self, relation_id: str) -> None:
        link = await self.get_link(relation_id)
        await self._run(link.delete)

    async def delete_issue_link(self, issue_id: str, relation_id: str) -> None:
        issue = await self.get_issue(issue_id)
        link = await self._run(issue.links.get, relation_id)
        await self._run(link.delete)

    async def get_queue(self, project_id: str) -> Any:
        return await self._run(self._get_client().queues.get, project_id)

    async def list_queues(self) -> list[Any]:
        return await self._run(self._get_client().queues.get_all)

    async def get_current_user(self) -> Any:
        return await self._run(lambda: self._get_client().myself)

    async def create_queue(self, data: dict[str, Any]) -> Any:
        return await self._run(
            self._get_client().queues.create,
            **data,
        )

    async def update_queue(self, queue: Any, data: dict[str, Any]) -> None:
        await self._run(queue.update, **data)

    async def delete_queue(self, queue: Any) -> None:
        await self._run(queue.delete)

