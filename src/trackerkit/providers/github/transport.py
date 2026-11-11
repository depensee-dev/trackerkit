import asyncio
from collections.abc import Callable
from typing import Any

import httpx

from trackerkit.contracts.auth import GitHubAuthConfig
from trackerkit.domain.enums import Provider
from trackerkit.domain.errors import ProviderError, get_error_kind
from trackerkit.domain.models import ConnectionDiagnostic
from trackerkit.providers.github.errors import GitHubNotFoundError, raise_github_error


class GitHubTransport:
    def __init__(self, config: GitHubAuthConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/"),
                timeout=self._config.timeout_seconds,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._config.access_token}",
                    "X-GitHub-Api-Version": self._config.api_version,
                    "User-Agent": "trackerkit",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        async with self._semaphore:
            try:
                response = await self._get_client().request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
            except httpx.HTTPError as error:
                detail = str(error) or type(error).__name__
                raise ProviderError(
                    f"GitHub API {method} {path} failed: {type(error).__name__}: {detail}"
                ) from error
        if response.status_code >= 400:
            raise_github_error(response, method, path)
        return response

    async def _paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
        item_filter: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        if limit is not None and limit <= 0:
            return []
        request_params = dict(params or {})
        request_params["per_page"] = 100 if limit is None else min(100, limit)
        request_params["page"] = 1
        result: list[dict[str, Any]] = []
        while True:
            response = await self._request("GET", path, params=request_params)
            payload = response.json()
            if not isinstance(payload, list):
                raise ProviderError(f"GitHub API GET {path} returned a non-list response.")
            for item in payload:
                if item_filter is None or item_filter(item):
                    result.append(item)
                    if limit is not None and len(result) >= limit:
                        return result
            if "next" not in response.links:
                return result
            request_params["page"] += 1

    @staticmethod
    def _repository_path(repository: dict[str, Any]) -> str:
        return f"/repos/{repository['full_name']}"

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        try:
            await self.get_current_user()
        except Exception as error:
            return ConnectionDiagnostic(
                provider=Provider.GITHUB,
                is_connected=False,
                error_kind=get_error_kind(error),
                message=str(error),
                error_type=type(error).__name__,
            )
        return ConnectionDiagnostic(provider=Provider.GITHUB, is_connected=True)

    async def check_connection(self) -> bool:
        diagnostic = await self.get_connection_diagnostic()
        return diagnostic.is_connected

    async def get_current_user(self) -> dict[str, Any]:
        response = await self._request("GET", "/user")
        return response.json()

    async def list_organizations(self) -> list[dict[str, Any]]:
        return await self._paginated("/user/orgs")

    async def list_repositories(self) -> list[dict[str, Any]]:
        return await self._paginated(
            "/user/repos",
            params={
                "affiliation": "owner,collaborator,organization_member",
                "visibility": "all",
                "sort": "updated",
                "direction": "desc",
            },
        )

    async def get_repository_by_id(self, repository_id: int) -> dict[str, Any]:
        response = await self._request("GET", f"/repositories/{repository_id}")
        return response.json()

    async def get_repository(self, full_name: str) -> dict[str, Any]:
        response = await self._request("GET", f"/repos/{full_name}")
        return response.json()

    async def list_issues(
        self,
        repository: dict[str, Any],
        params: dict[str, Any],
        limit: int | None,
    ) -> list[dict[str, Any]]:
        return await self._paginated(
            f"{self._repository_path(repository)}/issues",
            params=params,
            limit=limit,
            item_filter=lambda item: "pull_request" not in item,
        )

    async def count_issues(self, search_query: str) -> int:
        response = await self._request(
            "GET",
            "/search/issues",
            params={"q": search_query, "per_page": 1},
        )
        return int(response.json()["total_count"])

    async def get_issue(self, repository: dict[str, Any], issue_number: int) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"{self._repository_path(repository)}/issues/{issue_number}",
        )
        return response.json()

    async def create_issue(
        self,
        repository: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"{self._repository_path(repository)}/issues",
            json_body=data,
        )
        return response.json()

    async def update_issue(
        self,
        repository: dict[str, Any],
        issue_number: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "PATCH",
            f"{self._repository_path(repository)}/issues/{issue_number}",
            json_body=data,
        )
        return response.json()

    async def get_parent_issue(
        self,
        repository: dict[str, Any],
        issue_number: int,
    ) -> dict[str, Any] | None:
        try:
            response = await self._request(
                "GET",
                f"{self._repository_path(repository)}/issues/{issue_number}/parent",
            )
        except GitHubNotFoundError:
            return None
        return response.json()

    async def list_sub_issues(
        self,
        repository: dict[str, Any],
        issue_number: int,
    ) -> list[dict[str, Any]]:
        return await self._paginated(
            f"{self._repository_path(repository)}/issues/{issue_number}/sub_issues"
        )

    async def add_sub_issue(
        self,
        parent_repository: dict[str, Any],
        parent_issue_number: int,
        sub_issue_id: int,
    ) -> None:
        await self._request(
            "POST",
            f"{self._repository_path(parent_repository)}/issues/{parent_issue_number}/sub_issues",
            json_body={"sub_issue_id": sub_issue_id, "replace_parent": False},
        )

    async def remove_sub_issue(
        self,
        parent_repository: dict[str, Any],
        parent_issue_number: int,
        sub_issue_id: int,
    ) -> None:
        await self._request(
            "DELETE",
            f"{self._repository_path(parent_repository)}/issues/{parent_issue_number}/sub_issue",
            json_body={"sub_issue_id": sub_issue_id},
        )

    async def list_dependencies(
        self,
        repository: dict[str, Any],
        issue_number: int,
        direction: str,
    ) -> list[dict[str, Any]]:
        return await self._paginated(
            f"{self._repository_path(repository)}/issues/{issue_number}/dependencies/{direction}"
        )

    async def add_blocked_by(
        self,
        blocked_repository: dict[str, Any],
        blocked_issue_number: int,
        blocking_issue_id: int,
    ) -> None:
        await self._request(
            "POST",
            f"{self._repository_path(blocked_repository)}/issues/{blocked_issue_number}/dependencies/blocked_by",
            json_body={"issue_id": blocking_issue_id},
        )

    async def remove_blocked_by(
        self,
        blocked_repository: dict[str, Any],
        blocked_issue_number: int,
        blocking_issue_id: int,
    ) -> None:
        await self._request(
            "DELETE",
            f"{self._repository_path(blocked_repository)}/issues/{blocked_issue_number}/dependencies/blocked_by/{blocking_issue_id}",
        )

    async def list_related_issues(
        self,
        repository: dict[str, Any],
        issue_number: int,
    ) -> list[dict[str, Any]]:
        return await self._paginated(
            f"{self._repository_path(repository)}/issues/{issue_number}/relates_to"
        )

    async def add_related_issue(
        self,
        repository: dict[str, Any],
        issue_number: int,
        related_issue_id: int,
    ) -> None:
        await self._request(
            "POST",
            f"{self._repository_path(repository)}/issues/{issue_number}/relates_to",
            json_body={"issue_id": related_issue_id},
        )

    async def remove_related_issue(
        self,
        repository: dict[str, Any],
        issue_number: int,
        related_issue_id: int,
    ) -> None:
        await self._request(
            "DELETE",
            f"{self._repository_path(repository)}/issues/{issue_number}/relates_to/{related_issue_id}",
        )
