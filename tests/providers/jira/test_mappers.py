"""Unit tests for `JiraMapper` — datetime parsing, user/status fallbacks, workspace id (CORR-2, CORR-3)."""

from datetime import UTC, datetime

from trackerkit.providers.jira.mappers import JiraMapper


class _Attr:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_parse_datetime_with_z_suffix_returns_utc() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    parsed = mapper._parse_datetime("2025-01-02T10:30:00.000Z")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed == datetime(2025, 1, 2, 10, 30, tzinfo=UTC)


def test_parse_datetime_with_naive_string_normalizes_to_utc() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    parsed = mapper._parse_datetime("2025-01-02T10:30:00")
    assert parsed is not None
    assert parsed.tzinfo == UTC


def test_parse_datetime_with_date_only_returns_midnight_utc() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    parsed = mapper._parse_datetime("2025-01-02")
    assert parsed == datetime(2025, 1, 2, 0, 0, tzinfo=UTC)


def test_parse_datetime_returns_none_for_empty_inputs() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    assert mapper._parse_datetime(None) is None
    assert mapper._parse_datetime("") is None
    assert mapper._parse_datetime(123) is None


def test_parse_datetime_passes_through_existing_datetime() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    when = datetime(2025, 1, 2, 10, 30, tzinfo=UTC)
    assert mapper._parse_datetime(when) is when


def test_to_user_returns_none_when_all_attrs_are_none() -> None:
    """CORR-3: should not produce User(id='None')."""
    mapper = JiraMapper("https://jira.example.com/")
    user = mapper._to_user(_Attr())
    assert user is None


def test_to_user_uses_account_id_when_present() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    user = mapper._to_user(_Attr(accountId="acc-1", displayName="Alice", emailAddress="a@b.com"))
    assert user is not None
    assert user.id == "acc-1"
    assert user.display_name == "Alice"
    assert user.email == "a@b.com"


def test_to_user_falls_back_to_display_name_for_id() -> None:
    mapper = JiraMapper("https://jira.example.com/")
    user = mapper._to_user(_Attr(displayName="Alice"))
    assert user is not None
    assert user.id == "Alice"
    assert user.display_name == "Alice"


def test_to_workspace_uses_synthetic_id_not_url() -> None:
    """CORR-2: workspace id must not be the base URL itself."""
    mapper = JiraMapper("https://jira.example.com/")
    workspace = mapper.to_workspace()
    assert workspace.id == "jira:jira.example.com"
    assert workspace.id != "https://jira.example.com"
    assert workspace.key == "jira"


def test_to_workspace_id_strips_trailing_slash_and_uses_netloc() -> None:
    mapper = JiraMapper("https://jira.example.com/sub/")
    workspace = mapper.to_workspace()
    assert workspace.id == "jira:jira.example.com"


def test_to_task_maps_priority_and_issue_type(fake_jira_issue_payload: _Attr) -> None:
    fake_jira_issue_payload.fields.priority = _Attr(name="Highest")
    fake_jira_issue_payload.fields.issuetype = _Attr(name="Bug")
    task = JiraMapper("https://jira.example.com").to_task(fake_jira_issue_payload)
    assert task.priority is not None and task.priority.value == "high"
    assert task.work_type is not None and task.work_type.value == "bug"
