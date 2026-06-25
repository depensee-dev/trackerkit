"""Unit tests for `YandexTrackerQueryPolicy` — server-side query building (PERF-2)."""

from datetime import UTC, datetime

from trackerkit.domain.models import TaskQuery
from trackerkit.providers.yandex_tracker.queries import YandexTrackerQueryPolicy


def test_build_search_params_returns_none_query_when_no_filters() -> None:
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(None)
    assert params == {"query": None}


def test_build_search_params_scopes_queue_via_query_dsl() -> None:
    # The SDK's top-level ``queue`` kwarg is ignored by the search/count
    # endpoints, so the queue must be encoded in the query string instead.
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(TaskQuery(project_id="MY"))
    assert params["query"] == 'Queue: "MY"'


def test_build_search_params_combines_queue_with_other_filters() -> None:
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(
        TaskQuery(project_id="MY", assignee_id="alice")
    )
    assert params["query"] == 'Queue: "MY" Assignee: "alice"'


def test_build_search_params_pushes_assignee_to_server() -> None:
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(TaskQuery(assignee_id="alice"))
    assert params["query"] == 'Assignee: "alice"'


def test_build_search_params_pushes_status_to_server() -> None:
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(TaskQuery(status_id="In Progress"))
    assert params["query"] == 'Status: "In Progress"'


def test_build_search_params_combines_clauses_with_space() -> None:
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(
        TaskQuery(assignee_id="alice", status_id="Done")
    )
    assert params["query"] == 'Assignee: "alice" Status: "Done"'


def test_build_search_params_pushes_updated_since_to_server_as_iso_date() -> None:
    policy = YandexTrackerQueryPolicy()
    when = datetime(2025, 1, 2, 10, 30, tzinfo=UTC)
    params = policy.build_issue_search_params(TaskQuery(updated_since=when))
    assert 'Updated: >= "2025-01-02"' in (params["query"] or "")


def test_build_search_params_escapes_quote_in_filter_value() -> None:
    policy = YandexTrackerQueryPolicy()
    params = policy.build_issue_search_params(TaskQuery(assignee_id='ali"ce'))
    assert params["query"] == 'Assignee: "ali\\"ce"'
