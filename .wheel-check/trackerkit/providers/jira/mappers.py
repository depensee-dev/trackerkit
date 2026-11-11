import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from trackerkit.domain.models import Project, Status, Task, User, Workspace


class JiraMapper:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._workspace_id = self._build_workspace_id(self._base_url)

    @staticmethod
    def _build_workspace_id(base_url: str) -> str:
        # Synthetic, deliberately non-URL form so callers cannot misuse this id
        # as a real Jira API endpoint. Falls back to the original URL if parsing
        # fails (best-effort) but still prefixes it with ``jira:`` to keep the
        # value distinct from a usable URL.
        parsed = urlparse(base_url)
        host = parsed.netloc or base_url
        return f"jira:{host}"

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def to_workspace(self) -> Workspace:
        parsed = urlparse(self._base_url)
        return Workspace(
            id=self._workspace_id,
            name=parsed.netloc or self._base_url,
            key="jira",
        )

    def to_project(self, value: Any) -> Project:
        description = getattr(value, "description", None)
        if description is None and getattr(value, "raw", None):
            description = value.raw.get("description")
        return Project(
            id=str(value.id),
            name=str(value.name),
            key=getattr(value, "key", None),
            description=self._extract_description(description),
            workspace_id=self._workspace_id,
        )

    def to_task(self, issue: Any) -> Task:
        fields = issue.fields
        project = getattr(fields, "project", None)
        return Task(
            id=str(issue.id),
            key=getattr(issue, "key", None),
            title=str(getattr(fields, "summary", "")),
            description=self._extract_description(getattr(fields, "description", None)),
            project_id=str(project.id) if project is not None else None,
            status=self._to_status(getattr(fields, "status", None)),
            assignee=self._to_user(getattr(fields, "assignee", None)),
            reporter=self._to_user(getattr(fields, "reporter", None)),
            created_at=self._parse_datetime(getattr(fields, "created", None)),
            updated_at=self._parse_datetime(getattr(fields, "updated", None)),
            due_date=self._parse_datetime(getattr(fields, "duedate", None)),
            url=issue.permalink(),
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

    def _to_user(self, value: Any) -> User | None:
        if value is None:
            return None
        user_id = (
            getattr(value, "accountId", None)
            or getattr(value, "name", None)
            or getattr(value, "key", None)
            or getattr(value, "displayName", None)
        )
        if user_id is None:
            return None
        display_name = (
            getattr(value, "displayName", None)
            or getattr(value, "name", None)
            or getattr(value, "accountId", None)
            or user_id
        )
        return User(
            id=str(user_id),
            display_name=str(display_name),
            email=getattr(value, "emailAddress", None),
        )

    def _to_status(self, value: Any) -> Status | None:
        if value is None:
            return None
        category = getattr(getattr(value, "statusCategory", None), "name", None)
        return Status(
            id=str(getattr(value, "id", None) or getattr(value, "name", "")),
            name=str(getattr(value, "name", "")),
            category=category,
        )

    def _extract_description(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=True)

