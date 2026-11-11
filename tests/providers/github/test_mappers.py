from datetime import UTC, datetime

from trackerkit.providers.github.mappers import GitHubMapper


def test_to_task_maps_github_issue(
    fake_github_repository_payload: dict,
    fake_github_issue_payload: dict,
) -> None:
    mapper = GitHubMapper()
    task = mapper.to_task(fake_github_issue_payload, fake_github_repository_payload)
    assert task.id == "github:task:v1:10001:501:42"
    assert task.key == "octocat/project#42"
    assert task.title == "Demo issue"
    assert task.description == "Body"
    assert task.project_id == "501"
    assert task.status is not None
    assert task.status.id == "open"
    assert task.status.category == "todo"
    assert task.assignee is not None
    assert task.assignee.id == "octocat"
    assert task.reporter is not None
    assert task.reporter.id == "octocat"
    assert task.created_at == datetime(2025, 1, 1, 10, tzinfo=UTC)
    assert task.updated_at == datetime(2025, 1, 2, 11, tzinfo=UTC)
    assert task.due_date is None
    assert task.url == "https://github.com/octocat/project/issues/42"


def test_to_task_uses_first_assignee_and_closed_status(
    fake_github_repository_payload: dict,
    fake_github_issue_payload: dict,
) -> None:
    issue = {
        **fake_github_issue_payload,
        "state": "closed",
        "assignee": None,
        "assignees": [
            {"login": "alice"},
            {"login": "bob"},
        ],
    }
    task = GitHubMapper().to_task(issue, fake_github_repository_payload)
    assert task.status is not None
    assert task.status.id == "closed"
    assert task.status.category == "done"
    assert task.assignee is not None
    assert task.assignee.id == "alice"


def test_to_project_maps_repository_and_owner(
    fake_github_repository_payload: dict,
) -> None:
    project = GitHubMapper().to_project(fake_github_repository_payload)
    assert project.id == "501"
    assert project.name == "project"
    assert project.key == "octocat/project"
    assert project.description == "Demo repository"
    assert project.workspace_id == "github:user:77"


def test_to_workspace_maps_organization() -> None:
    workspace = GitHubMapper().to_workspace(
        {"id": 88, "login": "acme"},
        owner_type="Organization",
    )
    assert workspace.id == "github:org:88"
    assert workspace.name == "acme"
    assert workspace.key == "acme"


def test_to_user_returns_none_without_login() -> None:
    assert GitHubMapper()._to_user({"id": 77}) is None


def test_parse_datetime_normalizes_naive_value() -> None:
    parsed = GitHubMapper()._parse_datetime("2025-01-01T10:00:00")
    assert parsed == datetime(2025, 1, 1, 10, tzinfo=UTC)
    assert GitHubMapper()._parse_datetime("invalid") is None
