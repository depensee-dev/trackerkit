"""Unit tests for `YandexTrackerMapper` — user fallbacks (CORR-3)."""

from trackerkit.providers.yandex_tracker.mappers import YandexTrackerMapper


class _Attr:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_to_user_returns_none_when_all_attrs_are_none() -> None:
    mapper = YandexTrackerMapper("workspace-id")
    assert mapper._to_user(_Attr()) is None


def test_to_user_uses_uid_when_present() -> None:
    mapper = YandexTrackerMapper("workspace-id")
    user = mapper._to_user(_Attr(uid=42, login="alice", display="Alice"))
    assert user is not None
    assert user.id == "42"
    assert user.display_name == "Alice"


def test_to_user_falls_back_to_login_when_no_uid_or_id() -> None:
    mapper = YandexTrackerMapper("workspace-id")
    user = mapper._to_user(_Attr(login="alice"))
    assert user is not None
    assert user.id == "alice"
    assert user.display_name == "alice"


def test_to_task_maps_priority_and_type_by_provider_keys() -> None:
    issue = _Attr(
        id="1",
        key="QUEUE-1",
        summary="Demo",
        queue=_Attr(key="QUEUE"),
        priority={"key": "major", "display": "Высокий"},
        type={"key": "bug", "display": "Ошибка"},
    )
    task = YandexTrackerMapper("workspace-id").to_task(issue)
    assert task.priority is not None and task.priority.value == "high"
    assert task.work_type is not None and task.work_type.value == "bug"
