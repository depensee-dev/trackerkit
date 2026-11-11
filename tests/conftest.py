"""Shared pytest fixtures for trackerkit tests.

Most tests should not require live network access; provider transports are
substituted with light-weight fakes that return SDK-shaped dummy objects.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakeAttr:
    """SDK-style record with attribute access used by Jira/Yandex mappers."""

    _data: dict[str, Any] = field(default_factory=dict)

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, "_data", dict(kwargs))

    def __getattr__(self, item: str) -> Any:
        data = object.__getattribute__(self, "_data")
        if item in data:
            return data[item]
        raise AttributeError(item)


@pytest.fixture
def fake_jira_user_payload() -> FakeAttr:
    return FakeAttr(
        accountId="acc-1",
        displayName="Alice",
        emailAddress="alice@example.com",
    )


@pytest.fixture
def fake_jira_status_payload() -> FakeAttr:
    return FakeAttr(
        id="10000",
        name="In Progress",
        statusCategory=FakeAttr(name="indeterminate"),
    )


@pytest.fixture
def fake_jira_issue_payload(
    fake_jira_user_payload: FakeAttr,
    fake_jira_status_payload: FakeAttr,
) -> FakeAttr:
    fields = FakeAttr(
        summary="Demo issue",
        description="Body",
        project=FakeAttr(id="proj-1"),
        status=fake_jira_status_payload,
        assignee=fake_jira_user_payload,
        reporter=fake_jira_user_payload,
        created="2025-01-01T10:00:00.000+0000",
        updated="2025-01-02T11:00:00.000+0000",
        duedate="2025-02-01",
    )
    issue = FakeAttr(
        id="10001",
        key="PROJ-1",
        fields=fields,
    )
    object.__setattr__(
        issue,
        "_data",
        {
            **issue._data,
            "permalink": lambda: "https://jira.example.com/browse/PROJ-1",
        },
    )
    return issue


@pytest.fixture
def fake_yandex_user_payload() -> FakeAttr:
    return FakeAttr(
        uid=12345,
        login="alice",
        display="Alice",
        email="alice@example.com",
    )


@pytest.fixture
def fake_github_repository_payload() -> dict[str, Any]:
    return {
        "id": 501,
        "name": "project",
        "full_name": "octocat/project",
        "description": "Demo repository",
        "owner": {"id": 77, "login": "octocat", "type": "User"},
    }


@pytest.fixture
def fake_github_issue_payload() -> dict[str, Any]:
    return {
        "id": 10001,
        "number": 42,
        "title": "Demo issue",
        "body": "Body",
        "state": "open",
        "user": {"login": "octocat"},
        "assignee": {"login": "octocat"},
        "assignees": [{"login": "octocat"}],
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-02T11:00:00Z",
        "html_url": "https://github.com/octocat/project/issues/42",
        "repository_url": "https://api.github.com/repos/octocat/project",
    }


def pages(items: Iterable[Any]) -> list[Any]:
    """Helper: materialize an iterable into a list (mimics SDK paginator)."""
    return list(items)
