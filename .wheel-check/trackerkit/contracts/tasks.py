from abc import ABC, abstractmethod

from trackerkit.domain.models import CreateTaskInput, Task, TaskQuery, UpdateTaskInput


class TaskReadCapability(ABC):
    @abstractmethod
    async def get_task(self, task_id: str) -> Task:
        raise NotImplementedError

    @abstractmethod
    async def list_tasks(self, query: TaskQuery | None = None) -> list[Task]:
        raise NotImplementedError

    # Non-abstract on purpose: not every provider can count cheaply, so
    # adapters opt in by overriding instead of being forced to implement it.
    async def count_tasks(self, query: TaskQuery | None = None) -> int:
        raise NotImplementedError


class TaskWriteCapability(ABC):
    @abstractmethod
    async def create_task(self, payload: CreateTaskInput) -> Task:
        raise NotImplementedError

    @abstractmethod
    async def update_task(self, task_id: str, payload: UpdateTaskInput) -> Task:
        raise NotImplementedError

    @abstractmethod
    async def delete_task(self, task_id: str) -> None:
        raise NotImplementedError

