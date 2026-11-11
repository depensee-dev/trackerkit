from datetime import UTC, datetime
from typing import Any

from trackerkit.domain.errors import ProviderCapabilityError
from trackerkit.domain.models import TaskQuery


class GitHubQueryBuilder:
    def build_issue_params(self, query: TaskQuery | None) -> dict[str, Any]:
        effective_query = query or TaskQuery()
        self.validate_status(effective_query.status_id)
        params: dict[str, Any] = {
            "state": effective_query.status_id or "all",
            "sort": "updated",
            "direction": "desc",
        }
        if effective_query.assignee_id is not None:
            params["assignee"] = effective_query.assignee_id
        if effective_query.updated_since is not None:
            params["since"] = self._format_datetime(effective_query.updated_since)
        return params

    def build_search_query(self, repository_full_name: str, query: TaskQuery | None) -> str:
        effective_query = query or TaskQuery()
        self.validate_status(effective_query.status_id)
        clauses = [f"repo:{repository_full_name}", "is:issue"]
        if effective_query.assignee_id is not None:
            clauses.append(f'assignee:"{self._quote(effective_query.assignee_id)}"')
        if effective_query.status_id is not None:
            clauses.append(f"state:{effective_query.status_id}")
        if effective_query.updated_since is not None:
            updated_since = self._format_datetime(effective_query.updated_since)
            clauses.append(f"updated:>={updated_since}")
        return " ".join(clauses)

    @staticmethod
    def validate_status(status_id: str | None) -> None:
        if status_id not in {None, "open", "closed"}:
            raise ProviderCapabilityError(
                "GitHub issues support only 'open' and 'closed' status ids."
            )

    @staticmethod
    def _quote(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        normalized = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return normalized
