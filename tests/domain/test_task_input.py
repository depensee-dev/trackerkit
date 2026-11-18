import pytest
from pydantic import ValidationError

from trackerkit.domain.enums import TaskState
from trackerkit.domain.models import CreateTaskInput, UpdateTaskInput


def test_task_write_accepts_only_one_status_value() -> None:
    with pytest.raises(ValidationError):
        CreateTaskInput(title="Demo", status_id="10001", state=TaskState.DONE)


def test_update_distinguishes_omitted_fields_from_explicit_null() -> None:
    payload = UpdateTaskInput(title="Demo")
    assert payload.provides("title")
    assert not payload.provides("assignee_id")
    assert not payload.provides("due_date")

    cleared = UpdateTaskInput(assignee_id=None, due_date=None)
    assert cleared.provides("assignee_id")
    assert cleared.provides("due_date")
    assert cleared.assignee_id is None
