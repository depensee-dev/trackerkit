import asyncio
from typing import Any
from urllib.parse import urlparse

from trackerkit.contracts.auth import GitHubAuthConfig
from trackerkit.domain.enums import RelationType
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
from trackerkit.providers.github.identifiers import GitHubTaskHandle
from trackerkit.providers.github.mappers import GitHubMapper
from trackerkit.providers.github.queries import GitHubQueryBuilder
from trackerkit.providers.github.relations import GitHubRelationPolicy
from trackerkit.providers.github.transport import GitHubTransport


class GitHubClient(BaseTaskTrackerAdapter):
    provider_name = "GitHub"

    def __init__(
        self,
        config: GitHubAuthConfig,
        relation_mapping: RelationMappingConfig | None = None,
    ) -> None:
        self._transport = GitHubTransport(config)
        self._mapper = GitHubMapper()
        self._queries = GitHubQueryBuilder()
        self._relations = GitHubRelationPolicy()
        self._repository_cache: dict[str, dict[str, Any]] = {}

    async def check_connection(self) -> bool:
        return await self._transport.check_connection()

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        return await self._transport.get_connection_diagnostic()

    async def close(self) -> None:
        await self._transport.close()

    def _cache_repository(self, repository: dict[str, Any]) -> dict[str, Any]:
        self._repository_cache[str(repository["id"])] = repository
        self._repository_cache[str(repository["full_name"]).casefold()] = repository
        return repository

    async def _get_repository(self, project_id: str) -> dict[str, Any]:
        if not project_id.isdigit():
            raise ProviderError("GitHub project_id must be a numeric repository id.")
        cached = self._repository_cache.get(project_id)
        if cached is not None:
            return cached
        repository = await self._transport.get_repository_by_id(int(project_id))
        return self._cache_repository(repository)

    @staticmethod
    def _issue_repository_full_name(issue: dict[str, Any]) -> str | None:
        for key in ("repository_url", "url"):
            value = issue.get(key)
            if not isinstance(value, str):
                continue
            parts = [part for part in urlparse(value).path.split("/") if part]
            try:
                index = parts.index("repos")
                return f"{parts[index + 1]}/{parts[index + 2]}"
            except (ValueError, IndexError):
                continue
        return None

    async def _repository_for_issue(
        self,
        issue: dict[str, Any],
        default_repository: dict[str, Any],
    ) -> dict[str, Any]:
        embedded = issue.get("repository")
        if isinstance(embedded, dict) and embedded.get("id") is not None:
            return self._cache_repository(embedded)
        full_name = self._issue_repository_full_name(issue)
        if full_name is None:
            raise ProviderError("GitHub issue response does not identify its repository.")
        if full_name.casefold() == str(default_repository["full_name"]).casefold():
            return default_repository
        cached = self._repository_cache.get(full_name.casefold())
        if cached is not None:
            return cached
        repository = await self._transport.get_repository(full_name)
        return self._cache_repository(repository)

    async def _task_id_for_issue(
        self,
        issue: dict[str, Any],
        default_repository: dict[str, Any],
    ) -> str:
        repository = await self._repository_for_issue(issue, default_repository)
        return self._mapper.task_id(issue, repository)

    async def _read_issue(self, handle: GitHubTaskHandle) -> tuple[dict[str, Any], dict[str, Any]]:
        repository = await self._get_repository(str(handle.repository_id))
        issue = await self._transport.get_issue(repository, handle.issue_number)
        if int(issue.get("id", 0)) != handle.issue_id:
            raise ProviderError("GitHub task id does not match the issue returned by the API.")
        return issue, repository

    @staticmethod
    def _require_project_id(project_id: str | None) -> str:
        if project_id is None:
            raise ProviderCapabilityError(
                "GitHub task operations require project_id mapped to a repository id."
            )
        return project_id

    async def get_task(self, task_id: str) -> Task:
        issue, repository = await self._read_issue(GitHubTaskHandle.parse(task_id))
        return self._mapper.to_task(issue, repository)

    async def list_tasks(self, query: TaskQuery | None = None) -> list[Task]:
        effective_query = query or TaskQuery()
        project_id = self._require_project_id(effective_query.project_id)
        params = self._queries.build_issue_params(effective_query)
        repository = await self._get_repository(project_id)
        issues = await self._transport.list_issues(
            repository,
            params,
            effective_query.limit,
        )
        return [self._mapper.to_task(issue, repository) for issue in issues]

    async def count_tasks(self, query: TaskQuery | None = None) -> int:
        effective_query = query or TaskQuery()
        project_id = self._require_project_id(effective_query.project_id)
        repository = await self._get_repository(project_id)
        search_query = self._queries.build_search_query(
            str(repository["full_name"]),
            effective_query,
        )
        return await self._transport.count_issues(search_query)

    async def create_task(self, payload: CreateTaskInput) -> Task:
        project_id = self._require_project_id(payload.project_id)
        self._queries.validate_status(payload.status_id)
        if payload.due_date is not None:
            raise ProviderCapabilityError("GitHub issues do not have a native due_date field.")
        data: dict[str, Any] = {"title": payload.title}
        if payload.description is not None:
            data["body"] = payload.description
        if payload.assignee_id is not None:
            data["assignees"] = [payload.assignee_id]
        repository = await self._get_repository(project_id)
        issue = await self._transport.create_issue(repository, data)
        if payload.status_id == "closed":
            issue = await self._transport.update_issue(
                repository,
                int(issue["number"]),
                {"state": "closed"},
            )
        return self._mapper.to_task(issue, repository)

    async def update_task(self, task_id: str, payload: UpdateTaskInput) -> Task:
        self._queries.validate_status(payload.status_id)
        if payload.due_date is not None:
            raise ProviderCapabilityError("GitHub issues do not have a native due_date field.")
        handle = GitHubTaskHandle.parse(task_id)
        issue, repository = await self._read_issue(handle)
        data: dict[str, Any] = {}
        if payload.title is not None:
            data["title"] = payload.title
        if payload.description is not None:
            data["body"] = payload.description
        if payload.assignee_id is not None:
            data["assignees"] = [payload.assignee_id]
        if payload.status_id is not None:
            data["state"] = payload.status_id
        if data:
            issue = await self._transport.update_issue(
                repository,
                handle.issue_number,
                data,
            )
        return self._mapper.to_task(issue, repository)

    async def delete_task(self, task_id: str) -> None:
        raise self._unsupported("delete_task")

    async def list_workspaces(self) -> list[Workspace]:
        user, organizations = await asyncio.gather(
            self._transport.get_current_user(),
            self._transport.list_organizations(),
        )
        return [
            self._mapper.to_workspace(user, owner_type="User"),
            *(
                self._mapper.to_workspace(organization, owner_type="Organization")
                for organization in organizations
            ),
        ]

    async def get_project(self, project_id: str) -> Project:
        repository = await self._get_repository(project_id)
        return self._mapper.to_project(repository)

    async def list_projects(self, workspace_id: str | None = None) -> list[Project]:
        repositories = await self._transport.list_repositories()
        for repository in repositories:
            self._cache_repository(repository)
        projects = [self._mapper.to_project(repository) for repository in repositories]
        if workspace_id is not None:
            projects = [project for project in projects if project.workspace_id == workspace_id]
        return projects

    async def create_project(self, payload: CreateProjectInput) -> Project:
        raise self._unsupported("create_project")

    async def update_project(
        self,
        project_id: str,
        payload: UpdateProjectInput,
    ) -> Project:
        raise self._unsupported("update_project")

    async def delete_project(self, project_id: str) -> None:
        raise self._unsupported("delete_project")

    async def list_relations(self, task_id: str) -> list[Relation]:
        handle = GitHubTaskHandle.parse(task_id)
        repository = await self._get_repository(str(handle.repository_id))
        parent, sub_issues, blocked_by, blocking, related = await asyncio.gather(
            self._transport.get_parent_issue(repository, handle.issue_number),
            self._transport.list_sub_issues(repository, handle.issue_number),
            self._transport.list_dependencies(repository, handle.issue_number, "blocked_by"),
            self._transport.list_dependencies(repository, handle.issue_number, "blocking"),
            self._transport.list_related_issues(repository, handle.issue_number),
        )
        linked_issues = [
            issue
            for issue in [parent, *sub_issues, *blocked_by, *blocking, *related]
            if issue is not None
        ]
        unique_issues = {int(issue["id"]): issue for issue in linked_issues}
        linked_task_ids_list = await asyncio.gather(
            *(self._task_id_for_issue(issue, repository) for issue in unique_issues.values())
        )
        linked_task_ids = dict(zip(unique_issues, linked_task_ids_list, strict=True))
        current_task_id = str(handle)
        relations: list[Relation] = []
        if parent is not None:
            relations.append(
                self._relations.build_relation(
                    linked_task_ids[int(parent["id"])],
                    current_task_id,
                    RelationType.CONTAINS,
                )
            )
        for issue in sub_issues:
            relations.append(
                self._relations.build_relation(
                    current_task_id,
                    linked_task_ids[int(issue["id"])],
                    RelationType.CONTAINS,
                )
            )
        for issue in blocked_by:
            relations.append(
                self._relations.build_relation(
                    linked_task_ids[int(issue["id"])],
                    current_task_id,
                    RelationType.BLOCKS,
                )
            )
        for issue in blocking:
            relations.append(
                self._relations.build_relation(
                    current_task_id,
                    linked_task_ids[int(issue["id"])],
                    RelationType.BLOCKS,
                )
            )
        for issue in related:
            relations.append(
                self._relations.build_relation(
                    current_task_id,
                    linked_task_ids[int(issue["id"])],
                    RelationType.RELATES,
                )
            )
        unique_relations = {
            (
                relation.id,
                relation.source_task_id,
                relation.target_task_id,
                relation.relation_type,
            ): relation
            for relation in relations
        }
        return list(unique_relations.values())

    async def create_relation(self, payload: CreateRelationInput) -> Relation:
        relation = self._relations.build_relation(
            payload.source_task_id,
            payload.target_task_id,
            payload.relation_type,
        )
        source = GitHubTaskHandle.parse(relation.source_task_id)
        target = GitHubTaskHandle.parse(relation.target_task_id)
        if relation.relation_type is RelationType.CONTAINS:
            repository = await self._get_repository(str(source.repository_id))
            await self._transport.add_sub_issue(
                repository,
                source.issue_number,
                target.issue_id,
            )
        elif relation.relation_type is RelationType.BLOCKS:
            repository = await self._get_repository(str(target.repository_id))
            await self._transport.add_blocked_by(
                repository,
                target.issue_number,
                source.issue_id,
            )
        else:
            repository = await self._get_repository(str(source.repository_id))
            await self._transport.add_related_issue(
                repository,
                source.issue_number,
                target.issue_id,
            )
        return relation

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
        relation = self._relations.parse_relation_id(relation_id)
        source = GitHubTaskHandle.parse(relation.source_task_id)
        target = GitHubTaskHandle.parse(relation.target_task_id)
        if relation.relation_type is RelationType.CONTAINS:
            repository = await self._get_repository(str(source.repository_id))
            await self._transport.remove_sub_issue(
                repository,
                source.issue_number,
                target.issue_id,
            )
        elif relation.relation_type is RelationType.BLOCKS:
            repository = await self._get_repository(str(target.repository_id))
            await self._transport.remove_blocked_by(
                repository,
                target.issue_number,
                source.issue_id,
            )
        else:
            repository = await self._get_repository(str(source.repository_id))
            await self._transport.remove_related_issue(
                repository,
                source.issue_number,
                target.issue_id,
            )
