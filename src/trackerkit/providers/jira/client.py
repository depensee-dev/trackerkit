from typing import Any

from trackerkit.contracts.auth import JiraAuthConfig
from trackerkit.domain.enums import RelationType
from trackerkit.domain.errors import ProviderCapabilityError
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
from trackerkit.providers.jira.mappers import JiraMapper
from trackerkit.providers.jira.queries import JiraQueryBuilder
from trackerkit.providers.jira.relations import JiraRelationPolicy
from trackerkit.providers.jira.transport import JiraTransport


class JiraClient(BaseTaskTrackerAdapter):
    provider_name = "Jira"

    def __init__(
        self,
        config: JiraAuthConfig,
        relation_mapping: RelationMappingConfig | None = None,
    ) -> None:
        self._transport = JiraTransport(config)
        self._mapper = JiraMapper(config.base_url)
        self._queries = JiraQueryBuilder()
        effective_mapping = relation_mapping or RelationMappingConfig()
        self._relations = JiraRelationPolicy(effective_mapping.jira)

    async def check_connection(self) -> bool:
        return await self._transport.check_connection()

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        return await self._transport.get_connection_diagnostic()

    async def get_task(self, task_id: str) -> Task:
        issue = await self._transport.get_issue(task_id, self._queries.task_fields)
        return self._mapper.to_task(issue)

    async def list_tasks(self, query: TaskQuery | None = None) -> list[Task]:
        jql, fields = self._queries.build_task_search(query)
        issues = await self._transport.search_issues(jql, fields)
        return [self._mapper.to_task(issue) for issue in issues]

    async def count_tasks(self, query: TaskQuery | None = None) -> int:
        jql, _ = self._queries.build_task_search(query)
        return await self._transport.count_issues(jql)

    async def create_task(self, payload: CreateTaskInput) -> Task:
        if payload.project_id is None:
            raise ProviderCapabilityError("Jira task creation requires project_id.")
        fields: dict[str, Any] = {
            "project": payload.project_id,
            "issuetype": {"name": "Task"},
            "summary": payload.title,
        }
        if payload.description is not None:
            fields["description"] = payload.description
        if payload.assignee_id is not None:
            fields["assignee"] = {"accountId": payload.assignee_id}
        if payload.due_date is not None:
            fields["duedate"] = payload.due_date.date().isoformat()
        issue = await self._transport.create_issue(fields)
        if payload.status_id is not None:
            await self._transport.transition_issue(issue, payload.status_id)
        refreshed = await self._transport.get_issue(issue.key, self._queries.task_fields)
        return self._mapper.to_task(refreshed)

    async def update_task(self, task_id: str, payload: UpdateTaskInput) -> Task:
        issue = await self._transport.get_issue(task_id, self._queries.task_fields)
        fields: dict[str, Any] = {}
        if payload.title is not None:
            fields["summary"] = payload.title
        if payload.description is not None:
            fields["description"] = payload.description
        if payload.assignee_id is not None:
            fields["assignee"] = {"accountId": payload.assignee_id}
        if payload.due_date is not None:
            fields["duedate"] = payload.due_date.date().isoformat()
        if fields:
            # `Issue.update(fields=...)` already refreshes the local resource
            # via `find()` in pycontribs/jira, so no extra GET is needed when
            # we only changed fields.
            await self._transport.update_issue_fields(issue, fields)
        if payload.status_id is not None:
            # Transitions are POST-only and do not refresh the issue object,
            # so a single re-read is required to surface the new status.
            await self._transport.transition_issue(issue, payload.status_id)
            issue = await self._transport.get_issue(task_id, self._queries.task_fields)
        return self._mapper.to_task(issue)

    async def delete_task(self, task_id: str) -> None:
        await self._transport.delete_issue_by_id(task_id)

    async def list_workspaces(self) -> list[Workspace]:
        return [self._mapper.to_workspace()]

    async def get_project(self, project_id: str) -> Project:
        project = await self._transport.get_project(project_id)
        return self._mapper.to_project(project)

    async def list_projects(self, workspace_id: str | None = None) -> list[Project]:
        if workspace_id is not None and workspace_id != self._mapper.to_workspace().id:
            return []
        projects = await self._transport.get_projects()
        return [self._mapper.to_project(project) for project in projects]

    async def create_project(self, payload: CreateProjectInput) -> Project:
        if payload.key is None:
            raise ProviderCapabilityError("Jira project creation requires key.")
        project_id = await self._transport.create_project(
            key=payload.key,
            name=payload.name,
        )
        project = await self._transport.get_project(str(project_id))
        if payload.description is not None:
            return await self.update_project(
                str(project.id),
                UpdateProjectInput(description=payload.description),
            )
        return self._mapper.to_project(project)

    async def update_project(
        self,
        project_id: str,
        payload: UpdateProjectInput,
    ) -> Project:
        data: dict[str, Any] = {}
        if payload.name is not None:
            data["name"] = payload.name
        if payload.key is not None:
            data["key"] = payload.key
        if payload.description is not None:
            data["description"] = payload.description
        if data:
            await self._transport.update_project(project_id, data)
        return await self.get_project(project_id)

    async def delete_project(self, project_id: str) -> None:
        await self._transport.delete_project(project_id)

    async def list_relations(self, task_id: str) -> list[Relation]:
        issue = await self._transport.get_issue(task_id, self._relations.relation_fields)
        return self._relations.list_relations(issue)

    async def create_relation(self, payload: CreateRelationInput) -> Relation:
        if (
            payload.relation_type is RelationType.CONTAINS
            and self._relations.uses_structural_contains()
        ):
            await self._transport.set_issue_parent(
                payload.target_task_id,
                payload.source_task_id,
            )
            return self._relations.build_created_relation(None, payload)

        mapping = self._relations.get_create_link_mapping(payload.relation_type)
        if mapping is None:
            raise ProviderCapabilityError(
                f"Jira relation type '{payload.relation_type.value}' is not configured."
            )
        relation_id = await self._transport.create_issue_link(
            mapping.type_name,
            payload.source_task_id,
            payload.target_task_id,
        )
        if relation_id is None:
            source_relations = await self.list_relations(payload.source_task_id)
            created_relation = self._relations.find_relation(source_relations, payload)
            if created_relation is not None:
                return created_relation
        return self._relations.build_created_relation(relation_id, payload)

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
        structural_relation = self._relations.parse_structural_relation_id(relation_id)
        if structural_relation is not None:
            raise ProviderCapabilityError(
                "Jira structural 'contains' relations cannot be deleted safely via this adapter."
            )
        await self._transport.delete_issue_link(relation_id)

