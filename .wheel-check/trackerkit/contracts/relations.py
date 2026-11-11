from abc import ABC, abstractmethod

from trackerkit.domain.models import (
    CreateRelationInput,
    Relation,
    UpdateRelationInput,
)


class RelationCapability(ABC):
    @abstractmethod
    async def list_relations(self, task_id: str) -> list[Relation]:
        raise NotImplementedError

    @abstractmethod
    async def create_relation(self, payload: CreateRelationInput) -> Relation:
        raise NotImplementedError

    @abstractmethod
    async def update_relation(
        self,
        relation_id: str,
        payload: UpdateRelationInput,
    ) -> Relation:
        raise NotImplementedError

    @abstractmethod
    async def delete_relation(self, relation_id: str) -> None:
        raise NotImplementedError

