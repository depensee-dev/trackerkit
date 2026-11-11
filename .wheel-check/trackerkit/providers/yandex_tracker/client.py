from typing import Any

from trackerkit.contracts.auth import YandexTrackerAuthConfig
from trackerkit.domain.errors import ProviderCapabilityError, ProviderError
from trackerkit.domain.models import (
    ConnectionDiagnostic,
    CreateProjectInput,
    CreateRelationInput,
    CreateTaskInput,
    Project,
    Relation,
    Task,
    TaskQuery,
    UpdateProjectInput,
    UpdateRelationInput,
    UpdateTaskInput,
    Workspace,
)
from trackerkit.domain.relation_mapping import RelationMappingConfig
from trackerkit.providers.base import BaseTaskTrackerAdapter
from trackerkit.providers.yandex_tracker.mappers import YandexTrackerMapper
from trackerkit.providers.yandex_tracker.queries import YandexTrackerQueryPolicy
from trackerkit.providers.yandex_tracker.relations import (
    YandexTrackerRelationPolicy,
)
from trackerkit.providers.yandex_tracker.transport import YandexTrackerTransport


class YandexTrackerClient(BaseTaskTrackerAdapter):
    provider_name = "Yandex Tracker"

    def __init__(
        self,
        config: YandexTrackerAuthConfig,
        relation_mapping: RelationMappingConfig | None = None,
    ) -> None:
        workspace_id = str(
            config.cloud_org_id or config.org_id or "yandex-tracker"
        )
        self._transport = YandexTrackerTransport(config)
        self._mapper = YandexTrackerMapper(workspace_id)
        self._queries = YandexTrackerQueryPolicy()
        effective_mapping = relation_mapping or RelationMappingConfig()
        self._relations = YandexTrackerRelationPolicy(
            effective_mapping.yandex_tracker
        )

    async def check_connection(self) -> bool:
        return await self._transport.check_connection()

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        return await self._transport.get_connection_diagnostic()

    async def get_task(self, task_id: str) -> Task:
        issue = await self._transport.get_issue(task_id)
        return self._mapper.to_task(issue)

    async def list_tasks(self, query: TaskQuery | None = None) -> list[Task]:
        params = self._queries.build_issue_search_params(query)
        # Queue scoping is encoded in the query string (``Queue: KEY``) because
        # the SDK's top-level ``queue`` kwarg is ignored by the search endpoint.
        #
        # The Yandex SDK returns a ``PaginatedList`` that transparently follows
        # ``next`` links while it is iterated, so a single materialized fetch
        # already yields every matching issue across all pages. The transport
        # consumes that iterator inside a worker thread (see ``find_issues``),
        # which is why we must not page manually or call ``len()`` here.
        issues = await self._transport.find_issues(params["query"], 100)
        tasks = [self._mapper.to_task(issue) for issue in issues]
        return self._queries.filter_tasks(tasks, query)

    async def count_tasks(self, query: TaskQuery | None = None) -> int:
        params = self._queries.build_issue_search_params(query)
        # See ``list_tasks``: the queue is part of ``params["query"]``; the
        # ``/issues/_count`` endpoint likewise ignores a top-level ``queue``.
        return await self._transport.count_issues(params["query"])

    async def create_task(self, payload: CreateTaskInput) -> Task:
        if payload.project_id is None:
            raise ProviderCapabilityError(
                "Yandex Tracker task creation requires project_id mapped to queue key."
            )
        data: dict[str, Any] = {
            "queue": payload.project_id,
            "summary": payload.title,
        }
        if payload.description is not None:
            data["description"] = payload.description
        if payload.assignee_id is not None:
            data["assignee"] = payload.assignee_id
        if payload.status_id is not None:
            data["status"] = payload.status_id
        if payload.due_date is not None:
            data["deadline"] = payload.due_date.date().isoformat()
        issue = await self._transport.create_issue(data)
        return self._mapper.to_task(issue)

    async def update_task(self, task_id: str, payload: UpdateTaskInput) -> Task:
        issue = await self._transport.get_issue(task_id)
        data: dict[str, Any] = {}
        if payload.title is not None:
            data["summary"] = payload.title
        if payload.description is not None:
            data["description"] = payload.description
        if payload.assignee_id is not None:
            data["assignee"] = payload.assignee_id
        if payload.status_id is not None:
            data["status"] = payload.status_id
        if payload.due_date is not None:
            data["deadline"] = payload.due_date.date().isoformat()
        if data:
            await self._transport.update_issue(issue, data)
        return self._mapper.to_task(issue)

    async def delete_task(self, task_id: str) -> None:
        raise ProviderCapabilityError(
            "Yandex Tracker does not support direct issue deletion via this adapter. "
            "Close or move the issue instead, or delete the parent queue/project "
            "when the workflow allows it."
        )

    async def list_workspaces(self) -> list[Workspace]:
        return [self._mapper.to_workspace()]

    async def get_project(self, project_id: str) -> Project:
        queue = await self._transport.get_queue(project_id)
        return self._mapper.to_project(queue)

    async def list_projects(self, workspace_id: str | None = None) -> list[Project]:
        if workspace_id is not None and workspace_id != self._mapper.to_workspace().id:
            return []
        queues = await self._transport.list_queues()
        return [self._mapper.to_project(queue) for queue in queues]

    def _build_issue_types_config(self, queue: Any) -> list[dict[str, str]]:
        workflows = getattr(queue, "workflows", {}) or {}
        workflow_key = next(iter(workflows.keys()), None)
        if workflow_key is None:
            raise ProviderCapabilityError(
                "Yandex Tracker queue creation requires a workflow template."
            )

        issue_types = workflows.get(workflow_key) or []
        configs: list[dict[str, str]] = []
        for issue_type in issue_types:
            issue_type_key = getattr(issue_type, "key", None)
            if issue_type_key is not None:
                configs.append(
                    {
                        "issueType": str(issue_type_key),
                        "workflow": str(workflow_key),
                    }
                )

        if not configs:
            raise ProviderCapabilityError(
                "Yandex Tracker queue creation requires at least one issue type in workflow config."
            )
        return configs

    async def create_project(self, payload: CreateProjectInput) -> Project:
        if payload.key is None:
            raise ProviderCapabilityError(
                "Yandex Tracker project creation requires key mapped to queue key."
            )
        existing_queues = await self._transport.list_queues()
        if not existing_queues:
            raise ProviderCapabilityError(
                "Yandex Tracker project creation requires at least one existing queue "
                "to derive default workflow settings in this adapter."
            )

        template_queue = existing_queues[0]
        current_user = await self._transport.get_current_user()
        default_type = getattr(getattr(template_queue, "defaultType", None), "key", None)
        default_priority = getattr(
            getattr(template_queue, "defaultPriority", None),
            "key",
            None,
        )
        lead = getattr(current_user, "login", None)

        if default_type is None or default_priority is None or lead is None:
            raise ProviderCapabilityError(
                "Yandex Tracker queue creation requires lead, defaultType, and defaultPriority."
            )

        queue_payload = {
            "key": payload.key,
            "name": payload.name,
            "description": payload.description,
            "lead": str(lead),
            "defaultType": str(default_type),
            "defaultPriority": str(default_priority),
            "issueTypesConfig": self._build_issue_types_config(template_queue),
        }
        try:
            queue = await self._transport.create_queue(queue_payload)
        except ProviderError as error:
            message = str(error)
            if any(
                token in message
                for token in (
                    "defaultPriority",
                    "defaultType",
                    "issueTypesConfig",
                    "lead",
                    "/v2/workflows/",
                )
            ):
                raise ProviderCapabilityError(
                    "Yandex Tracker queue creation requires additional queue settings "
                    "(lead, defaultType, defaultPriority, issueTypesConfig/workflow) "
                    "and corresponding permissions for the current account."
                ) from error
            raise
        return self._mapper.to_project(queue)

    async def update_project(
        self,
        project_id: str,
        payload: UpdateProjectInput,
    ) -> Project:
        if payload.key is not None and payload.key != project_id:
            raise ProviderCapabilityError(
                "Yandex Tracker does not support queue key change in this adapter."
            )
        queue = await self._transport.get_queue(project_id)
        data: dict[str, Any] = {}
        if payload.name is not None:
            data["name"] = payload.name
        if payload.description is not None:
            data["description"] = payload.description
        if data:
            await self._transport.update_queue(queue, data)
        return self._mapper.to_project(queue)

    async def delete_project(self, project_id: str) -> None:
        queue = await self._transport.get_queue(project_id)
        await self._transport.delete_queue(queue)

    async def list_relations(self, task_id: str) -> list[Relation]:
        issue = await self._transport.get_issue(task_id)
        links = await self._transport.get_issue_links(issue)
        return self._relations.list_relations(issue, links)

    async def create_relation(self, payload: CreateRelationInput) -> Relation:
        relationship = self._relations.get_create_relationship(payload.relation_type)
        if relationship is None:
            raise ProviderCapabilityError(
                f"Yandex Tracker relation type '{payload.relation_type.value}' is not configured."
            )
        source_issue = await self._transport.get_issue(payload.source_task_id)
        link = await self._transport.create_issue_link(
            source_issue,
            relationship,
            payload.target_task_id,
        )
        return self._relations.build_created_relation(str(link.id), payload)

    async def update_relation(
        self,
        relation_id: str,
        payload: UpdateRelationInput,
    ) -> Relation:
        await self.delete_relation(relation_id)
        return await self.create_relation(
            CreateRelationInput(
                source_task_id=payload.source_task_id,
                target_task_id=payload.target_task_id,
                relation_type=payload.relation_type,
            )
        )

    async def delete_relation(self, relation_id: str) -> None:
        parsed_relation_id = self._relations.split_relation_id(relation_id)
        if parsed_relation_id is None:
            await self._transport.delete_link(relation_id)
            return
        issue_id, link_id = parsed_relation_id
        await self._transport.delete_issue_link(issue_id, link_id)

