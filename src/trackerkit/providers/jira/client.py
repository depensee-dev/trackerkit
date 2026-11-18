from typing import Any

from trackerkit.contracts.auth import JiraAuthConfig
from trackerkit.domain.enums import RelationType, TaskPriority, TaskState, TaskWorkType
from trackerkit.domain.errors import ProviderCapabilityError, ProviderError
from trackerkit.domain.models import (
    Comment,
    ConnectionDiagnostic,
    CreateCommentInput,
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
from trackerkit.providers.jira.metadata import (
    priority_name,
    select_transition_id,
    work_type_name,
)
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
        self._priority_names: dict[str, str] | None = None
        self._issue_type_names: dict[str, dict[str, str]] = {}

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
        issue_type = await self._issue_type_name(payload.project_id, payload.work_type)
        fields: dict[str, Any] = {
            "project": payload.project_id,
            "issuetype": {"name": issue_type or "Task"},
            "summary": payload.title,
        }
        if payload.description is not None:
            fields["description"] = payload.description
        if payload.assignee_id is not None:
            fields["assignee"] = {"accountId": payload.assignee_id}
        if payload.due_date is not None:
            fields["duedate"] = payload.due_date.date().isoformat()
        priority = await self._priority_field(payload.priority)
        if priority is not None:
            fields["priority"] = priority
        issue = await self._transport.create_issue(fields)
        await self._apply_state(issue, payload.status_id, payload.state)
        refreshed = await self._transport.get_issue(issue.key, self._queries.task_fields)
        return self._mapper.to_task(refreshed)

    async def update_task(self, task_id: str, payload: UpdateTaskInput) -> Task:
        issue = await self._transport.get_issue(task_id, self._queries.task_fields)
        fields: dict[str, Any] = {}
        if payload.provides("title") and payload.title is not None:
            fields["summary"] = payload.title
        if payload.provides("description"):
            fields["description"] = payload.description or ""
        if payload.provides("assignee_id"):
            fields["assignee"] = (
                {"accountId": payload.assignee_id} if payload.assignee_id is not None else None
            )
        if payload.provides("due_date"):
            fields["duedate"] = (
                payload.due_date.date().isoformat() if payload.due_date is not None else None
            )
        if payload.provides("priority") and payload.priority is not None:
            priority = await self._priority_field(payload.priority)
            if priority is not None:
                fields["priority"] = priority
        if payload.provides("work_type") and payload.work_type is not None:
            project = getattr(issue.fields, "project", None)
            project_id = str(getattr(project, "id", "") or "")
            issue_type = await self._issue_type_name(project_id, payload.work_type)
            if issue_type is not None:
                fields["issuetype"] = {"name": issue_type}
        if fields:
            # `Issue.update(fields=...)` already refreshes the local resource
            # via `find()` in pycontribs/jira, so no extra GET is needed when
            # we only changed fields.
            await self._transport.update_issue_fields(issue, fields)
        changed_state = await self._apply_state(issue, payload.status_id, payload.state)
        if changed_state:
            issue = await self._transport.get_issue(task_id, self._queries.task_fields)
        return self._mapper.to_task(issue)

    async def list_comments(self, task_id: str) -> list[Comment]:
        comments = await self._transport.list_comments(task_id)
        return [self._mapper.to_comment(task_id, comment) for comment in comments]

    async def create_comment(self, payload: CreateCommentInput) -> Comment:
        comment = await self._transport.add_comment(payload.task_id, payload.body)
        return self._mapper.to_comment(payload.task_id, comment)

    async def _apply_state(
        self,
        issue: Any,
        status_id: str | None,
        state: TaskState | None,
    ) -> bool:
        if status_id is not None:
            await self._transport.transition_issue(issue, status_id)
            return True
        if state is None:
            return False
        raw_transitions = await self._transport.list_transitions(issue)
        transitions = [_transition_dict(item) for item in raw_transitions]
        transition_id = select_transition_id(transitions, state)
        if transition_id is None:
            return False
        await self._transport.transition_issue(issue, transition_id)
        return True

    async def _priority_field(self, priority: TaskPriority | None) -> dict[str, str] | None:
        if priority is None:
            return None
        names = await self._load_priority_names()
        name = names.get(priority_name(priority).casefold())
        if name is None:
            return None
        return {"name": name}

    async def _issue_type_name(
        self,
        project_id: str,
        work_type: TaskWorkType | None,
    ) -> str | None:
        if work_type is None:
            return None
        names = await self._load_issue_type_names(project_id)
        return names.get(work_type_name(work_type).casefold())

    async def _load_priority_names(self) -> dict[str, str]:
        if self._priority_names is not None:
            return self._priority_names
        try:
            priorities = await self._transport.list_priorities()
        except ProviderError:
            return {}
        self._priority_names = {
            str(getattr(item, "name", "")).casefold(): str(getattr(item, "name", ""))
            for item in priorities
            if getattr(item, "name", None)
        }
        return self._priority_names

    async def _load_issue_type_names(self, project_id: str) -> dict[str, str]:
        cached = self._issue_type_names.get(project_id)
        if cached is not None:
            return cached
        try:
            issue_types = await self._transport.list_project_issue_types(project_id)
        except ProviderError:
            return {}
        names = {
            str(getattr(item, "name", "")).casefold(): str(getattr(item, "name", ""))
            for item in issue_types
            if getattr(item, "name", None)
        }
        self._issue_type_names[project_id] = names
        return names

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


def _transition_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raw = getattr(value, "raw", None)
    if isinstance(raw, dict):
        return raw
    return {}
