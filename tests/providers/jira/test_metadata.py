from trackerkit.domain.enums import TaskPriority, TaskWorkType
from trackerkit.providers.jira.metadata import normalize_priority, normalize_work_type


def test_jira_priority_mapping_uses_documented_levels() -> None:
    assert normalize_priority("Lowest") is TaskPriority.LOW
    assert normalize_priority("Low") is TaskPriority.LOW
    assert normalize_priority("Medium") is TaskPriority.MEDIUM
    assert normalize_priority("High") is TaskPriority.HIGH
    assert normalize_priority("Highest") is TaskPriority.HIGH


def test_jira_work_type_mapping_is_explicit() -> None:
    assert normalize_work_type("Bug") is TaskWorkType.BUG
    assert normalize_work_type("Story") is TaskWorkType.FEATURE
    assert normalize_work_type("Task") is TaskWorkType.TASK
    assert normalize_work_type("Sub-task") is TaskWorkType.TASK
    assert normalize_work_type("Refactoring") is TaskWorkType.REFACTOR


def test_jira_unknown_metadata_is_not_guessed() -> None:
    assert normalize_priority("Urgent") is None
    assert normalize_work_type("Epic") is None
