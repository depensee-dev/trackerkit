from trackerkit.domain.enums import TaskPriority, TaskWorkType
from trackerkit.providers.yandex_tracker.metadata import (
    normalize_priority,
    normalize_work_type,
)


def test_yandex_priority_mapping_uses_provider_keys() -> None:
    assert normalize_priority("trivial") is TaskPriority.LOW
    assert normalize_priority("minor") is TaskPriority.LOW
    assert normalize_priority("normal") is TaskPriority.MEDIUM
    assert normalize_priority("major") is TaskPriority.HIGH
    assert normalize_priority("critical") is TaskPriority.HIGH
    assert normalize_priority("blocker") is TaskPriority.HIGH


def test_yandex_work_type_mapping_is_explicit() -> None:
    assert normalize_work_type("bug") is TaskWorkType.BUG
    assert normalize_work_type("story") is TaskWorkType.FEATURE
    assert normalize_work_type("improvement") is TaskWorkType.FEATURE
    assert normalize_work_type("newFeature") is TaskWorkType.FEATURE
    assert normalize_work_type("task") is TaskWorkType.TASK
    assert normalize_work_type("subtask") is TaskWorkType.TASK
    assert normalize_work_type("refactoring") is TaskWorkType.REFACTOR


def test_yandex_unknown_metadata_is_not_guessed() -> None:
    assert normalize_priority("urgent") is None
    assert normalize_work_type("epic") is None
