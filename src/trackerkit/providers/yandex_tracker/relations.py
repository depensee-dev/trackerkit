from typing import Any, ClassVar

from trackerkit.domain.enums import RelationType
from trackerkit.domain.models import CreateRelationInput, Relation
from trackerkit.domain.relation_mapping import (
    YandexTrackerRelationMapping,
    YandexTrackerRelationMappingConfig,
)


class YandexTrackerRelationPolicy:
    _RELATION_ID_SEPARATOR = ":"
    _TYPE_ID_ALIASES: ClassVar[dict[str, RelationType]] = {
        "relates": RelationType.RELATES,
        "subtask": RelationType.CONTAINS,
        "parent": RelationType.CONTAINS,
        "dependency": RelationType.BLOCKS,
        "dependent": RelationType.BLOCKS,
        "depends": RelationType.BLOCKS,
        "blocks": RelationType.BLOCKS,
        "is dependent by": RelationType.BLOCKS,
        "depends on": RelationType.BLOCKS,
        "is parent task for": RelationType.CONTAINS,
        "is subtask for": RelationType.CONTAINS,
    }

    def __init__(self, config: YandexTrackerRelationMappingConfig) -> None:
        self._config = config

    def list_relations(self, issue: Any, links: list[Any]) -> list[Relation]:
        relations: list[Relation] = []
        current_issue_id = str(issue.id)
        for link in links:
            relation = self._to_relation_from_issue_context(current_issue_id, link)
            if relation is not None:
                relations.append(relation)
        return relations

    def get_create_relationship(self, relation_type) -> str | None:
        mapping = self._find_mapping_by_relation_type(relation_type)
        if mapping is None:
            return None
        return mapping.outward_value

    def build_relation_id(self, issue_id: str, link_id: str | None) -> str | None:
        if link_id is None:
            return None
        return f"{issue_id}{self._RELATION_ID_SEPARATOR}{link_id}"

    def split_relation_id(self, relation_id: str) -> tuple[str, str] | None:
        if self._RELATION_ID_SEPARATOR not in relation_id:
            return None
        issue_id, link_id = relation_id.split(self._RELATION_ID_SEPARATOR, 1)
        if not issue_id or not link_id:
            return None
        return issue_id, link_id

    def build_created_relation(
        self,
        relation_id: str | None,
        payload: CreateRelationInput,
    ) -> Relation:
        return Relation(
            id=self.build_relation_id(payload.source_task_id, relation_id),
            source_task_id=payload.source_task_id,
            target_task_id=payload.target_task_id,
            relation_type=payload.relation_type,
        )

    def _to_relation_from_issue_context(
        self,
        current_issue_id: str,
        link: Any,
    ) -> Relation | None:
        link_type = getattr(link, "type", None)
        direction = getattr(link, "direction", None)
        if link_type is None or direction not in {"inward", "outward"}:
            return None

        link_type_id = getattr(link_type, "id", None)
        current_label = (
            getattr(link_type, "outward", None)
            if direction == "outward"
            else getattr(link_type, "inward", None)
        )
        relation_type = self._find_relation_type(link_type_id, current_label)
        if relation_type is None:
            return None

        linked_object = getattr(link, "object", None)
        linked_issue_id = getattr(linked_object, "id", None)
        if linked_issue_id is None:
            return None

        if self._is_outward_direction(relation_type, direction, current_label):
            source_task_id = current_issue_id
            target_task_id = str(linked_issue_id)
        else:
            source_task_id = str(linked_issue_id)
            target_task_id = current_issue_id

        link_id = str(getattr(link, "id", "")) or None
        return Relation(
            id=self.build_relation_id(current_issue_id, link_id),
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            relation_type=relation_type,
        )

    def _find_relation_type(
        self,
        type_id: str | None,
        label: str | None,
    ) -> RelationType | None:
        mapping = self._find_mapping_by_label(label)
        if mapping is not None:
            return mapping.relation_type
        normalized_type_id = self._normalize(type_id)
        if normalized_type_id is None:
            return None
        return self._TYPE_ID_ALIASES.get(normalized_type_id)

    def _is_outward_direction(
        self,
        relation_type: RelationType,
        direction: str,
        label: str | None,
    ) -> bool:
        mapping = self._find_mapping_by_relation_type(relation_type)
        if mapping is not None and label is not None:
            normalized_label = self._normalize(label)
            if normalized_label == self._normalize(mapping.outward_value):
                return True
            if normalized_label == self._normalize(mapping.inward_value):
                return False
        if relation_type is RelationType.RELATES:
            return True
        if relation_type is RelationType.BLOCKS:
            return direction == "inward"
        return direction == "outward"

    def _find_mapping_by_label(
        self,
        label: str | None,
    ) -> YandexTrackerRelationMapping | None:
        normalized_label = self._normalize(label)
        if normalized_label is None:
            return None
        for mapping in self._config.mappings:
            if normalized_label in {
                self._normalize(mapping.outward_value),
                self._normalize(mapping.inward_value),
            }:
                return mapping
        return None

    def _find_mapping_by_relation_type(
        self,
        relation_type,
    ) -> YandexTrackerRelationMapping | None:
        for mapping in self._config.mappings:
            if mapping.relation_type is relation_type:
                return mapping
        return None

    def _normalize(self, value: str | None) -> str | None:
        if value is None:
            return None
        return value.casefold().strip()
