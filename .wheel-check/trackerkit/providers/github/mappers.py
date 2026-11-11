from datetime import UTC, datetime
from typing import Any

from trackerkit.domain.models import Project, Status, Task, User, Workspace
from trackerkit.providers.github.identifiers import GitHubTaskHandle


class GitHubMapper:
    def to_workspace(self, value: dict[str, Any], *, owner_type: str | None = None) -> Workspace:
        resolved_type = owner_type or str(value.get("type") or "User")
        kind = "org" if resolved_type.casefold() in {"org", "organization"} else "user"
        login = str(value.get("login") or value["id"])
        return Workspace(
            id=f"github:{kind}:{value['id']}",
            name=str(value.get("name") or login),
            key=login,
        )

    def to_project(self, repository: dict[str, Any]) -> Project:
        owner = repository.get("owner") or {}
        return Project(
            id=str(repository["id"]),
            name=str(repository["name"]),
            key=str(repository["full_name"]),
            description=repository.get("description"),
            workspace_id=self.to_workspace(owner).id,
        )

    def task_id(self, issue: dict[str, Any], repository: dict[str, Any]) -> str:
        return str(
            GitHubTaskHandle(
                issue_id=int(issue["id"]),
                repository_id=int(repository["id"]),
                issue_number=int(issue["number"]),
            )
        )

    def to_task(self, issue: dict[str, Any], repository: dict[str, Any]) -> Task:
        assignee = issue.get("assignee")
        if assignee is None:
            assignees = issue.get("assignees") or []
            assignee = assignees[0] if assignees else None
        return Task(
            id=self.task_id(issue, repository),
            key=f"{repository['full_name']}#{issue['number']}",
            title=str(issue.get("title") or ""),
            description=issue.get("body"),
            project_id=str(repository["id"]),
            status=self._to_status(str(issue.get("state") or "open")),
            assignee=self._to_user(assignee),
            reporter=self._to_user(issue.get("user")),
            created_at=self._parse_datetime(issue.get("created_at")),
            updated_at=self._parse_datetime(issue.get("updated_at")),
            due_date=None,
            url=issue.get("html_url"),
        )

    def _to_user(self, value: dict[str, Any] | None) -> User | None:
        if not value or not value.get("login"):
            return None
        login = str(value["login"])
        return User(
            id=login,
            display_name=str(value.get("name") or login),
            email=value.get("email"),
        )

    def _to_status(self, state: str) -> Status:
        return Status(
            id=state,
            name=state.capitalize(),
            category="done" if state == "closed" else "todo",
        )

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
