from trackerkit.contracts.task_tracker_client import TaskTrackerClient
from trackerkit.domain.errors import ProviderCapabilityError
from trackerkit.domain.models import (
    Comment,
    CreateCommentInput,
    CreateRelationInput,
    Relation,
    TaskQuery,
    UpdateRelationInput,
    User,
)


class BaseTaskTrackerAdapter(TaskTrackerClient):
    """Base adapter with explicit unsupported capability handling."""

    provider_name = "provider"

    def _unsupported(self, operation: str) -> ProviderCapabilityError:
        return ProviderCapabilityError(
            f"{self.provider_name} does not support '{operation}' in this adapter."
        )

    async def count_tasks(self, query: TaskQuery | None = None) -> int:
        raise self._unsupported("count_tasks")

    async def list_users(self) -> list[User]:
        raise self._unsupported("list_users")

    async def list_comments(self, task_id: str) -> list[Comment]:
        raise self._unsupported("list_comments")

    async def create_comment(self, payload: CreateCommentInput) -> Comment:
        raise self._unsupported("create_comment")

    async def list_relations(self, task_id: str) -> list[Relation]:
        raise self._unsupported("list_relations")

    async def create_relation(self, payload: CreateRelationInput) -> Relation:
        raise self._unsupported("create_relation")

    async def update_relation(
        self,
        relation_id: str,
        payload: UpdateRelationInput,
    ) -> Relation:
        raise self._unsupported("update_relation")

    async def delete_relation(self, relation_id: str) -> None:
        raise self._unsupported("delete_relation")

