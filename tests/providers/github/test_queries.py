from datetime import UTC, datetime

import pytest

from trackerkit.domain.errors import ProviderCapabilityError
from trackerkit.domain.models import TaskQuery
from trackerkit.providers.github.queries import GitHubQueryBuilder


def test_issue_params_default_to_all_states() -> None:
    assert GitHubQueryBuilder().build_issue_params(None) == {
        "state": "all",
        "sort": "updated",
        "direction": "desc",
    }


def test_issue_params_include_supported_filters() -> None:
    params = GitHubQueryBuilder().build_issue_params(
        TaskQuery(
            assignee_id="octocat",
            status_id="closed",
            updated_since=datetime(2025, 1, 2, 10, 30),
        )
    )
    assert params["assignee"] == "octocat"
    assert params["state"] == "closed"
    assert params["since"] == "2025-01-02T10:30:00Z"


def test_issue_params_normalize_updated_since_to_utc() -> None:
    params = GitHubQueryBuilder().build_issue_params(
        TaskQuery(updated_since=datetime(2025, 1, 2, 13, 30, tzinfo=UTC))
    )
    assert params["since"] == "2025-01-02T13:30:00Z"


def test_search_query_excludes_pull_requests_and_combines_filters() -> None:
    query = GitHubQueryBuilder().build_search_query(
        "octocat/project",
        TaskQuery(
            assignee_id='octo"cat',
            status_id="open",
            updated_since=datetime(2025, 1, 2, 10, 30),
        ),
    )
    assert "repo:octocat/project" in query
    assert "is:issue" in query
    assert 'assignee:"octo\\"cat"' in query
    assert "state:open" in query
    assert "updated:>=2025-01-02T10:30:00Z" in query


@pytest.mark.parametrize("status_id", ["in_progress", "done"])
def test_invalid_status_is_an_explicit_capability_error(status_id: str) -> None:
    with pytest.raises(ProviderCapabilityError):
        GitHubQueryBuilder().build_issue_params(TaskQuery(status_id=status_id))
