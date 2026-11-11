from abc import ABC, abstractmethod

from trackerkit.domain.models import (
    CreateProjectInput,
    Project,
    UpdateProjectInput,
    Workspace,
)


class WorkspaceCapability(ABC):
    @abstractmethod
    async def list_workspaces(self) -> list[Workspace]:
        raise NotImplementedError


class ProjectReadCapability(ABC):
    @abstractmethod
    async def get_project(self, project_id: str) -> Project:
        raise NotImplementedError

    @abstractmethod
    async def list_projects(self, workspace_id: str | None = None) -> list[Project]:
        raise NotImplementedError


class ProjectWriteCapability(ABC):
    @abstractmethod
    async def create_project(self, payload: CreateProjectInput) -> Project:
        raise NotImplementedError

    @abstractmethod
    async def update_project(
        self,
        project_id: str,
        payload: UpdateProjectInput,
    ) -> Project:
        raise NotImplementedError

    @abstractmethod
    async def delete_project(self, project_id: str) -> None:
        raise NotImplementedError

