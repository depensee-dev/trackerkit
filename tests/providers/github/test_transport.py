import httpx
import pytest

from trackerkit.contracts.auth import GitHubAuthConfig
from trackerkit.domain.enums import ConnectionErrorKind, Provider
from trackerkit.providers.github.transport import GitHubTransport


def _transport(handler) -> GitHubTransport:
    transport = GitHubTransport(GitHubAuthConfig(access_token="secret"))
    transport._client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    return transport


@pytest.mark.asyncio
async def test_list_issues_paginates_and_excludes_pull_requests() -> None:
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        requested_pages.append(page)
        if page == 1:
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "number": 1},
                    {"id": 2, "number": 2, "pull_request": {}},
                ],
                headers={"Link": '<https://api.github.com/page=2>; rel="next"'},
            )
        return httpx.Response(200, json=[{"id": 3, "number": 3}])

    transport = _transport(handler)
    issues = await transport.list_issues(
        {"id": 10, "full_name": "octocat/project"},
        {"state": "all"},
        limit=None,
    )
    assert [issue["id"] for issue in issues] == [1, 3]
    assert requested_pages == [1, 2]
    await transport.close()


@pytest.mark.asyncio
async def test_list_issues_honors_limit_after_filtering() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"id": 1, "pull_request": {}},
                {"id": 2},
                {"id": 3},
            ],
        )

    transport = _transport(handler)
    issues = await transport.list_issues(
        {"id": 10, "full_name": "octocat/project"},
        {},
        limit=1,
    )
    assert [issue["id"] for issue in issues] == [2]
    await transport.close()


@pytest.mark.asyncio
async def test_parent_issue_404_means_no_parent() -> None:
    transport = _transport(lambda request: httpx.Response(404, json={"message": "Not Found"}))
    assert await transport.get_parent_issue({"full_name": "octocat/project"}, 1) is None
    await transport.close()


@pytest.mark.asyncio
async def test_connection_diagnostic_normalizes_authentication_error() -> None:
    transport = _transport(lambda request: httpx.Response(401, json={"message": "Bad credentials"}))
    diagnostic = await transport.get_connection_diagnostic()
    assert diagnostic.provider is Provider.GITHUB
    assert diagnostic.is_connected is False
    assert diagnostic.error_kind is ConnectionErrorKind.AUTHENTICATION
    assert diagnostic.message is not None
    assert "Bad credentials" in diagnostic.message
    await transport.close()


@pytest.mark.asyncio
async def test_rate_limit_error_contains_retry_after() -> None:
    transport = _transport(
        lambda request: httpx.Response(
            403,
            json={"message": "secondary rate limit"},
            headers={"Retry-After": "17"},
        )
    )
    diagnostic = await transport.get_connection_diagnostic()
    assert diagnostic.is_connected is False
    assert diagnostic.message is not None
    assert "retry after 17 seconds" in diagnostic.message
    await transport.close()


@pytest.mark.asyncio
async def test_delete_issue_posts_graphql_delete_issue_mutation() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"data": {"deleteIssue": {"clientMutationId": None}}})

    transport = _transport(handler)
    await transport.delete_issue("I_kwDOA")
    assert seen["path"] == "/graphql"
    assert isinstance(seen["body"], str)
    assert "deleteIssue" in seen["body"]
    assert "I_kwDOA" in seen["body"]
    await transport.close()


@pytest.mark.asyncio
async def test_permission_error_does_not_report_rate_limit_reset() -> None:
    transport = _transport(
        lambda request: httpx.Response(
            403,
            json={"message": "Resource not accessible by personal access token"},
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Reset": "1794422777"},
        )
    )
    diagnostic = await transport.get_connection_diagnostic()
    assert diagnostic.is_connected is False
    assert diagnostic.message is not None
    assert "Resource not accessible" in diagnostic.message
    assert "rate limit" not in diagnostic.message.casefold()
    await transport.close()


@pytest.mark.asyncio
async def test_organization_issue_fields_use_the_org_route() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(
            403,
            json={"message": "Resource not accessible by personal access token"},
            headers={"X-RateLimit-Remaining": "4999"},
        )

    transport = _transport(handler)
    fields = await transport.list_issue_fields(
        {
            "full_name": "depensee-dev/trackerkit",
            "owner": {"login": "depensee-dev", "type": "Organization"},
        }
    )
    assert fields == []
    assert seen == ["/orgs/depensee-dev/issue-fields"]
    await transport.close()


@pytest.mark.asyncio
async def test_user_owned_repository_reads_the_authenticated_users_fields() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "octocat", "id": 1})
        return httpx.Response(
            200,
            json=[{"id": 2, "name": "Priority", "data_type": "single_select", "options": []}],
        )

    transport = _transport(handler)
    fields = await transport.list_issue_fields(
        {
            "full_name": "octocat/project",
            "owner": {"login": "octocat", "type": "User"},
        }
    )
    assert [field["name"] for field in fields] == ["Priority"]
    assert seen == ["/user", "/user/issue-fields"]
    await transport.close()


@pytest.mark.asyncio
async def test_issue_types_are_read_from_the_repository() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=[{"id": 1, "name": "Bug", "is_enabled": True}])

    transport = _transport(handler)
    types = await transport.list_issue_types(
        {
            "full_name": "depensee-dev/trackerkit",
            "owner": {"login": "depensee-dev", "type": "Organization"},
        }
    )
    assert types[0]["name"] == "Bug"
    assert seen == ["/repos/depensee-dev/trackerkit/issue-types"]
    await transport.close()


@pytest.mark.asyncio
async def test_network_error_preserves_exception_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("")

    transport = _transport(handler)
    diagnostic = await transport.get_connection_diagnostic()
    assert diagnostic.is_connected is False
    assert diagnostic.message is not None
    assert "ReadTimeout" in diagnostic.message
    await transport.close()
