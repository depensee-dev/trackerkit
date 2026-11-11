from typing import Any
from unittest.mock import AsyncMock

import pytest

from trackerkit.contracts.auth import GitHubAuthConfig
from trackerkit.domain.enums import RelationType
from trackerkit.domain.errors import ProviderCapabilityError, ProviderError
from trackerkit.domain.models import (
    CreateProjectInput,
    CreateRelationInput,
    CreateTaskInput,
    TaskQuery,
    UpdateProjectInput,
    UpdateTaskInput,
)
from trackerkit.providers.github.client import GitHubClient
from trackerkit.providers.github.identifiers import GitHubTaskHandle


def _repository(repository_id: int = 501, name: str = "project") -> dict[str, Any]:
    return {
        "id": repository_id,
        "name": name,
        "full_name": f"octocat/{name}",
        "description": "Demo repository",
        "owner": {"id": 77, "login": "octocat", "type": "User"},
    }


def _issue(
    issue_id: int = 10001,
    number: int = 42,
    repository: dict[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    repository = repository or _repository()
    return {
        "id": issue_id,
        "number": number,
        "title": "Demo issue",
        "body": "Body",
        "state": "open",
        "user": {"login": "octocat"},
        "assignee": None,
        "assignees": [],
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-02T11:00:00Z",
        "html_url": f"https://github.com/{repository['full_name']}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repository['full_name']}",
        "repository": repository,
        **overrides,
    }


def _client(repositories: list[dict[str, Any]] | None = None) -> GitHubClient:
    client = GitHubClient(GitHubAuthConfig(access_token="secret"))
    repositories = repositories or [_repository()]
    by_id = {int(repository["id"]): repository for repository in repositories}
    transport = AsyncMock()
    transport.get_repository_by_id.side_effect = lambda repository_id: by_id[repository_id]
    transport.get_repository.side_effect = lambda full_name: next(
        repository for repository in repositories if repository["full_name"] == full_name
    )
    transport.list_repositories.return_value = repositories
    client._transport = transport
    return client


def _task_id(issue_id: int = 10001, number: int = 42, repository_id: int = 501) -> str:
    return str(GitHubTaskHandle(issue_id, repository_id, number))


@pytest.mark.asyncio
async def test_list_and_count_tasks_require_repository() -> None:
    client = _client()
    with pytest.raises(ProviderCapabilityError):
        await client.list_tasks()
    with pytest.raises(ProviderCapabilityError):
        await client.count_tasks()


@pytest.mark.asyncio
async def test_list_tasks_maps_issues_and_honors_limit() -> None:
    repository = _repository()
    client = _client([repository])
    client._transport.list_issues.return_value = [_issue(repository=repository)]
    query = TaskQuery(project_id="501", status_id="open", limit=1)
    tasks = await client.list_tasks(query)
    assert len(tasks) == 1
    assert tasks[0].id == _task_id()
    client._transport.list_issues.assert_awaited_once_with(
        repository,
        {"state": "open", "sort": "updated", "direction": "desc"},
        1,
    )


@pytest.mark.asyncio
async def test_count_tasks_uses_issue_search() -> None:
    client = _client()
    client._transport.count_issues.return_value = 7
    count = await client.count_tasks(TaskQuery(project_id="501", status_id="closed"))
    assert count == 7
    client._transport.count_issues.assert_awaited_once_with(
        "repo:octocat/project is:issue state:closed"
    )


@pytest.mark.asyncio
async def test_create_task_supports_closed_status() -> None:
    repository = _repository()
    client = _client([repository])
    created = _issue(repository=repository)
    client._transport.create_issue.return_value = created
    client._transport.update_issue.return_value = {**created, "state": "closed"}
    task = await client.create_task(
        CreateTaskInput(
            title="Demo",
            description="Body",
            project_id="501",
            assignee_id="octocat",
            status_id="closed",
        )
    )
    assert task.status is not None and task.status.id == "closed"
    client._transport.create_issue.assert_awaited_once_with(
        repository,
        {"title": "Demo", "body": "Body", "assignees": ["octocat"]},
    )
    client._transport.update_issue.assert_awaited_once_with(
        repository,
        42,
        {"state": "closed"},
    )


@pytest.mark.asyncio
async def test_create_task_rejects_due_date_before_writing() -> None:
    client = _client()
    with pytest.raises(ProviderCapabilityError):
        await client.create_task(
            CreateTaskInput(
                title="Demo",
                project_id="501",
                due_date="2025-01-02T00:00:00Z",
            )
        )
    client._transport.create_issue.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_and_update_task_use_stable_handle() -> None:
    repository = _repository()
    issue = _issue(repository=repository)
    client = _client([repository])
    client._transport.get_issue.return_value = issue
    client._transport.update_issue.return_value = {
        **issue,
        "title": "Updated",
        "state": "closed",
    }
    fetched = await client.get_task(_task_id())
    assert fetched.title == "Demo issue"
    updated = await client.update_task(
        _task_id(),
        UpdateTaskInput(title="Updated", status_id="closed", assignee_id="alice"),
    )
    assert updated.title == "Updated"
    client._transport.update_issue.assert_awaited_once_with(
        repository,
        42,
        {"title": "Updated", "assignees": ["alice"], "state": "closed"},
    )


@pytest.mark.asyncio
async def test_get_task_rejects_mismatched_issue_id() -> None:
    client = _client()
    client._transport.get_issue.return_value = _issue(issue_id=99999)
    with pytest.raises(ProviderError):
        await client.get_task(_task_id())


@pytest.mark.asyncio
async def test_list_workspaces_and_filter_projects() -> None:
    organization_repository = {
        **_repository(502, "org-project"),
        "owner": {"id": 88, "login": "acme", "type": "Organization"},
    }
    client = _client([_repository(), organization_repository])
    client._transport.get_current_user.return_value = {
        "id": 77,
        "login": "octocat",
        "name": "Octo Cat",
    }
    client._transport.list_organizations.return_value = [{"id": 88, "login": "acme"}]
    workspaces = await client.list_workspaces()
    assert [workspace.id for workspace in workspaces] == ["github:user:77", "github:org:88"]
    projects = await client.list_projects("github:org:88")
    assert [project.id for project in projects] == ["502"]


@pytest.mark.asyncio
async def test_list_relations_normalizes_all_core_types() -> None:
    repository = _repository()
    client = _client([repository])
    parent = _issue(10002, 1, repository)
    child = _issue(10003, 2, repository)
    blocker = _issue(10004, 3, repository)
    blocked = _issue(10005, 4, repository)
    related = _issue(10006, 5, repository)
    client._transport.get_parent_issue.return_value = parent
    client._transport.list_sub_issues.return_value = [child]
    client._transport.list_dependencies.side_effect = [[blocker], [blocked]]
    client._transport.list_related_issues.return_value = [related]
    relations = await client.list_relations(_task_id())
    by_type = {
        (relation.relation_type, relation.source_task_id, relation.target_task_id): relation
        for relation in relations
    }
    assert len(relations) == 5
    assert by_type[(RelationType.CONTAINS, _task_id(10002, 1), _task_id())]
    assert by_type[(RelationType.CONTAINS, _task_id(), _task_id(10003, 2))]
    assert by_type[(RelationType.BLOCKS, _task_id(10004, 3), _task_id())]
    assert by_type[(RelationType.BLOCKS, _task_id(), _task_id(10005, 4))]
    assert by_type[(RelationType.RELATES, _task_id(), _task_id(10006, 5))]


@pytest.mark.asyncio
@pytest.mark.parametrize("relation_type", list(RelationType))
async def test_relation_create_and_delete_use_native_endpoints(relation_type: RelationType) -> None:
    repository = _repository()
    client = _client([repository])
    payload = CreateRelationInput(
        source_task_id=_task_id(10001, 42),
        target_task_id=_task_id(10002, 43),
        relation_type=relation_type,
    )
    relation = await client.create_relation(payload)
    assert relation.id is not None
    await client.delete_relation(relation.id)
    if relation_type is RelationType.CONTAINS:
        client._transport.add_sub_issue.assert_awaited_once_with(repository, 42, 10002)
        client._transport.remove_sub_issue.assert_awaited_once_with(repository, 42, 10002)
    elif relation_type is RelationType.BLOCKS:
        client._transport.add_blocked_by.assert_awaited_once_with(repository, 43, 10001)
        client._transport.remove_blocked_by.assert_awaited_once_with(repository, 43, 10001)
    else:
        client._transport.add_related_issue.assert_awaited_once_with(repository, 42, 10002)
        client._transport.remove_related_issue.assert_awaited_once_with(repository, 42, 10002)


@pytest.mark.asyncio
async def test_unsupported_writes_are_explicit() -> None:
    client = _client()
    with pytest.raises(ProviderCapabilityError):
        await client.delete_task(_task_id())
    with pytest.raises(ProviderCapabilityError):
        await client.create_project(CreateProjectInput(name="demo"))
    with pytest.raises(ProviderCapabilityError):
        await client.update_project("501", UpdateProjectInput(name="demo"))
    with pytest.raises(ProviderCapabilityError):
        await client.delete_project("501")


@pytest.mark.asyncio
async def test_close_closes_transport() -> None:
    client = _client()
    await client.close()
    client._transport.close.assert_awaited_once()
