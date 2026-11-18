from datetime import datetime
from typing import Self

from pydantic import BaseModel, model_validator

from trackerkit.domain.enums import (
    ConnectionErrorKind,
    Provider,
    RelationType,
    TaskPriority,
    TaskState,
    TaskWorkType,
)


class User(BaseModel):
    id: str
    display_name: str
    email: str | None = None


class Workspace(BaseModel):
    id: str
    name: str
    key: str | None = None


class ConnectionDiagnostic(BaseModel):
    provider: Provider
    is_connected: bool
    # Pydantic accepts both the enum and its string value (it's a `str` enum),
    # so existing callers passing literals like ``"authentication"`` keep working.
    error_kind: ConnectionErrorKind | None = None
    message: str | None = None
    error_type: str | None = None


class Project(BaseModel):
    id: str
    name: str
    key: str | None = None
    description: str | None = None
    workspace_id: str | None = None


class Status(BaseModel):
    id: str
    name: str
    category: str | None = None


class Task(BaseModel):
    id: str
    key: str | None = None
    title: str
    description: str | None = None
    project_id: str | None = None
    status: Status | None = None
    state: TaskState | None = None
    priority: TaskPriority | None = None
    work_type: TaskWorkType | None = None
    assignee: User | None = None
    reporter: User | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None
    url: str | None = None


class Comment(BaseModel):
    id: str
    task_id: str
    body: str
    author: User | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Relation(BaseModel):
    id: str | None = None
    source_task_id: str
    target_task_id: str
    relation_type: RelationType


class TaskQuery(BaseModel):
    project_id: str | None = None
    assignee_id: str | None = None
    status_id: str | None = None
    updated_since: datetime | None = None
    # Soft cap on the number of items the adapter materializes from a paginated
    # provider response. Currently honored by GitHub (`list_tasks`); Jira/Yandex
    # ignore it because they already use bounded server-side queries.
    limit: int | None = None


class _TaskWrite(BaseModel):
    """Shared task write fields.

    On update, a field that was not passed is left unchanged. An explicit
    ``None`` clears that field when the provider has somewhere to clear it.
    ``status_id`` is a provider status. ``state`` is the portable open/done
    value. One call carries only one of them.
    """

    @model_validator(mode="after")
    def _one_status_value(self) -> Self:
        if self.status_id is not None and self.state is not None:
            raise ValueError("Pass either status_id or state.")
        return self

    def provides(self, field_name: str) -> bool:
        return field_name in self.model_fields_set


class CreateTaskInput(_TaskWrite):
    title: str
    description: str | None = None
    project_id: str | None = None
    assignee_id: str | None = None
    status_id: str | None = None
    state: TaskState | None = None
    priority: TaskPriority | None = None
    work_type: TaskWorkType | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None


class UpdateTaskInput(_TaskWrite):
    title: str | None = None
    description: str | None = None
    assignee_id: str | None = None
    status_id: str | None = None
    state: TaskState | None = None
    priority: TaskPriority | None = None
    work_type: TaskWorkType | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None


class CreateCommentInput(BaseModel):
    task_id: str
    body: str


class CreateProjectInput(BaseModel):
    name: str
    key: str | None = None
    description: str | None = None
    workspace_id: str | None = None


class UpdateProjectInput(BaseModel):
    name: str | None = None
    key: str | None = None
    description: str | None = None


class CreateRelationInput(BaseModel):
    source_task_id: str
    target_task_id: str
    relation_type: RelationType


class UpdateRelationInput(BaseModel):
    source_task_id: str
    target_task_id: str
    relation_type: RelationType
