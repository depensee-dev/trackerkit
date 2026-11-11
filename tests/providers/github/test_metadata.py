from trackerkit.domain.enums import TaskPriority, TaskWorkType
from trackerkit.providers.github.metadata import normalize_priority, normalize_work_type


def test_github_priority_mapping_uses_exact_field_values() -> None:
    assert normalize_priority("Low") is TaskPriority.LOW
    assert normalize_priority("Medium") is TaskPriority.MEDIUM
    assert normalize_priority("High") is TaskPriority.HIGH


def test_github_work_type_mapping_is_explicit() -> None:
    assert normalize_work_type("Bug") is TaskWorkType.BUG
    assert normalize_work_type("Feature") is TaskWorkType.FEATURE
    assert normalize_work_type("Task") is TaskWorkType.TASK
    assert normalize_work_type("Refactor") is TaskWorkType.REFACTOR


def test_github_unknown_metadata_is_not_guessed() -> None:
    assert normalize_priority("Critical") is None
    assert normalize_work_type("Enhancement") is None
