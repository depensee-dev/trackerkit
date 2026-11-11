from datetime import UTC, datetime
from typing import Any

from trackerkit.domain.models import Project, Status, Task, User, Workspace
from trackerkit.providers.yandex_tracker.metadata import normalize_priority, normalize_work_type


class YandexTrackerMapper:
    def __init__(self, workspace_id: str) -> None:
        self._workspace_id = workspace_id

    def to_workspace(self) -> Workspace:
        return Workspace(
            id=self._workspace_id,
            name="Yandex Tracker",
            key="yandex-tracker",
        )

    def to_project(self, queue: Any) -> Project:
        return Project(
            id=str(getattr(queue, "key", None) or getattr(queue, "id", "")),
            name=str(getattr(queue, "name", "")),
            key=getattr(queue, "key", None),
            description=getattr(queue, "description", None),
            workspace_id=self._workspace_id,
        )

    def to_task(self, issue: Any) -> Task:
        queue = getattr(issue, "queue", None)
        return Task(
            id=str(issue.id),
            key=getattr(issue, "key", None),
            title=str(getattr(issue, "summary", None) or getattr(issue, "title", "")),
            description=getattr(issue, "description", None),
            project_id=getattr(queue, "key", None) if queue is not None else None,
            status=self._to_status(getattr(issue, "status", None)),
            priority=normalize_priority(self._metadata_value(getattr(issue, "priority", None))),
            work_type=normalize_work_type(self._metadata_value(getattr(issue, "type", None))),
            assignee=self._to_user(getattr(issue, "assignee", None)),
            reporter=self._to_user(getattr(issue, "createdBy", None)),
            created_at=self._parse_datetime(getattr(issue, "createdAt", None)),
            updated_at=self._parse_datetime(getattr(issue, "updatedAt", None)),
            due_date=self._parse_datetime(getattr(issue, "deadline", None)),
            url=getattr(issue, "self", None),
        )

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(f"{normalized}T00:00:00")
            except ValueError:
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _short_value(self, value: Any) -> dict[str, Any]:
        # Read only the already-loaded ("short") representation of a Yandex SDK
        # Reference/Resource. ``as_dict()`` returns the payload that arrived with
        # the search response and never triggers a lazy per-object dereference.
        # Touching a missing attribute (e.g. ``uid``/``email``) on a Reference
        # would otherwise fetch the full user one HTTP call at a time — an N+1
        # storm when mapping a whole page of issues.
        if isinstance(value, dict):
            return value
        as_dict = getattr(value, "as_dict", None)
        if callable(as_dict):
            data = as_dict()
            if isinstance(data, dict):
                return data
        keys = ("uid", "id", "login", "display", "firstName", "email", "key", "name")
        return {key: getattr(value, key, None) for key in keys}

    def _metadata_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        data = self._short_value(value)
        result = data.get("key") or data.get("name") or data.get("display")
        return str(result) if result is not None else None

    def _to_user(self, value: Any) -> User | None:
        if value is None:
            return None
        data = self._short_value(value)
        user_id = data.get("uid") or data.get("id") or data.get("login") or data.get("display")
        if user_id is None:
            return None
        display_name = (
            data.get("display")
            or data.get("login")
            or data.get("firstName")
            or data.get("id")
            or user_id
        )
        return User(
            id=str(user_id),
            display_name=str(display_name),
            email=data.get("email"),
        )

    def _to_status(self, value: Any) -> Status | None:
        if value is None:
            return None
        return Status(
            id=str(getattr(value, "key", None) or getattr(value, "id", "")),
            name=str(getattr(value, "display", None) or getattr(value, "key", "")),
            category=None,
        )
