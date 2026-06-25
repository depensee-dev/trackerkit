from trackerkit.domain.models import Task, TaskQuery


class YandexTrackerQueryPolicy:
    def build_issue_search_params(self, query: TaskQuery | None) -> dict:
        effective_query = query or TaskQuery()
        return {
            "query": self._build_query_string(effective_query),
        }

    @staticmethod
    def _quote(value: str) -> str:
        # Yandex Tracker query language uses double-quoted string literals;
        # escape backslash and double-quote to prevent breaking out of them.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _build_query_string(self, query: TaskQuery) -> str | None:
        clauses: list[str] = []
        if query.project_id is not None:
            # Filter by queue via the query DSL. The SDK's top-level ``queue``
            # kwarg is NOT honored by ``/issues/_search`` and ``/issues/_count``
            # (they return issues across all queues), so encoding it here is the
            # only reliable way to scope both listing and counting to one queue.
            clauses.append(f"Queue: {self._quote(query.project_id)}")
        if query.assignee_id is not None:
            clauses.append(f"Assignee: {self._quote(query.assignee_id)}")
        if query.status_id is not None:
            clauses.append(f"Status: {self._quote(query.status_id)}")
        if query.updated_since is not None:
            # Yandex Tracker query DSL accepts ``Updated: >= "YYYY-MM-DD"``.
            iso_date = query.updated_since.date().isoformat()
            clauses.append(f'Updated: >= "{iso_date}"')
        if not clauses:
            return None
        return " ".join(clauses)

    def filter_tasks(self, tasks: list[Task], query: TaskQuery | None) -> list[Task]:
        # Defense-in-depth: the server query already narrows results, but we
        # re-check on the client side to keep behavior identical when the
        # provider cannot honor a particular field (e.g. unsupported status).
        effective_query = query or TaskQuery()
        filtered = tasks

        if effective_query.project_id is not None:
            filtered = [
                task
                for task in filtered
                if task.project_id == effective_query.project_id
            ]

        if effective_query.assignee_id is not None:
            filtered = [
                task
                for task in filtered
                if task.assignee is not None and task.assignee.id == effective_query.assignee_id
            ]

        if effective_query.status_id is not None:
            filtered = [
                task
                for task in filtered
                if task.status is not None and task.status.id == effective_query.status_id
            ]

        if effective_query.updated_since is not None:
            filtered = [
                task
                for task in filtered
                if task.updated_at is not None and task.updated_at >= effective_query.updated_since
            ]

        return filtered

