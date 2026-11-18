from trackerkit.domain.enums import TaskPriority, TaskWorkType
from trackerkit.providers.github.fields import build_catalog
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


def test_github_catalog_matches_priority_and_prefers_due_date() -> None:
    catalog = build_catalog(
        [{"name": "Bug", "is_enabled": True}, {"name": "Retired", "is_enabled": False}],
        [
            {
                "id": 4,
                "name": "Target date",
                "data_type": "date",
            },
            {
                "id": 5,
                "name": "Due date",
                "data_type": "date",
            },
            {
                "id": 2,
                "name": "Priority",
                "data_type": "single_select",
                "options": [{"name": "High"}],
            },
        ],
    )
    assert catalog.type_name(TaskWorkType.BUG) == "Bug"
    assert catalog.type_name(TaskWorkType.REFACTOR) is None
    assert catalog.priority is not None
    assert catalog.priority_option(TaskPriority.HIGH) == "High"
    assert catalog.due_date is not None
    assert catalog.due_date.id == 5


def test_github_unknown_metadata_is_not_guessed() -> None:
    assert normalize_priority("Critical") is None
    assert normalize_work_type("Enhancement") is None
