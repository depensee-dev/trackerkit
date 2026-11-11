from typing import Any

from trackerkit.domain.enums import RelationType
from trackerkit.domain.models import CreateRelationInput, Relation
from trackerkit.domain.relation_mapping import (
    JiraContainsMode,
    JiraLinkTypeMapping,
    JiraRelationMappingConfig,
)


class JiraRelationPolicy:
    relation_fields = "issuelinks,parent,subtasks"
    structural_prefix = "jira-contains"

    def __init__(self, config: JiraRelationMappingConfig) -> None:
        self._config = config

    def list_relations(self, issue: Any) -> list[Relation]:
        relations: list[Relation] = []
        issue_id = str(issue.id)

        for link in getattr(issue.fields, "issuelinks", []) or []:
            relation = self._to_relation_from_issue_context(issue_id, link)
            if relation is not None:
                relations.append(relation)

        if self.uses_structural_contains():
            parent = getattr(issue.fields, "parent", None)
            if parent is not None and getattr(parent, "id", None) is not None:
                relations.append(
                    Relation(
                        id=self.build_structural_relation_id(str(parent.id), issue_id),
                        source_task_id=str(parent.id),
                        target_task_id=issue_id,
                        relation_type=RelationType.CONTAINS,
                    )
                )
            for subtask in getattr(issue.fields, "subtasks", []) or []:
                if getattr(subtask, "id", None) is None:
                    continue
                relations.append(
                    Relation(
                        id=self.build_structural_relation_id(issue_id, str(subtask.id)),
                        source_task_id=issue_id,
                        target_task_id=str(subtask.id),
                        relation_type=RelationType.CONTAINS,
                    )
                )

        unique: dict[tuple[str | None, str, str, RelationType], Relation] = {}
        for relation in relations:
            unique[
                (
                    relation.id,
                    relation.source_task_id,
                    relation.target_task_id,
                    relation.relation_type,
                )
            ] = relation
        return list(unique.values())

    def build_created_relation(
        self,
        relation_id: str | None,
        payload: CreateRelationInput,
    ) -> Relation:
        if payload.relation_type is RelationType.CONTAINS and self.uses_structural_contains():
            relation_id = self.build_structural_relation_id(
                payload.source_task_id,
                payload.target_task_id,
            )
        return Relation(
            id=relation_id,
            source_task_id=payload.source_task_id,
            target_task_id=payload.target_task_id,
            relation_type=payload.relation_type,
        )

    def find_relation(
        self,
        relations: list[Relation],
        payload: CreateRelationInput,
    ) -> Relation | None:
        for relation in relations:
            if (
                relation.source_task_id == payload.source_task_id
                and relation.target_task_id == payload.target_task_id
                and relation.relation_type is payload.relation_type
            ):
                return relation
        return None

    def uses_structural_contains(self) -> bool:
        return self._config.contains_mode in {
            JiraContainsMode.STRUCTURAL_HIERARCHY,
            JiraContainsMode.HYBRID,
        }

    def uses_custom_contains_links(self) -> bool:
        return self._config.contains_mode in {
            JiraContainsMode.CUSTOM_LINK_MAPPING,
            JiraContainsMode.HYBRID,
        }

    def get_create_link_mapping(
        self,
        relation_type: RelationType,
    ) -> JiraLinkTypeMapping | None:
        if relation_type is RelationType.CONTAINS:
            if not self.uses_custom_contains_links():
                return None
            return self._config.contains_link_mappings[0] if self._config.contains_link_mappings else None

        for mapping in self._config.link_mappings:
            if mapping.relation_type is relation_type:
                return mapping
        return None

    def parse_global_relation(self, link: Any) -> Relation | None:
        relation_type = self._match_relation_type(getattr(link, "type", None))
        outward_issue = getattr(link, "outwardIssue", None)
        inward_issue = getattr(link, "inwardIssue", None)
        if relation_type is None or outward_issue is None or inward_issue is None:
            return None
        outward_id = getattr(outward_issue, "id", None)
        inward_id = getattr(inward_issue, "id", None)
        if outward_id is None or inward_id is None:
            return None
        return Relation(
            id=str(getattr(link, "id", "")) or None,
            source_task_id=str(outward_id),
            target_task_id=str(inward_id),
            relation_type=relation_type,
        )

    def build_structural_relation_id(self, parent_task_id: str, child_task_id: str) -> str:
        return f"{self.structural_prefix}:{parent_task_id}:{child_task_id}"

    def parse_structural_relation_id(self, relation_id: str) -> tuple[str, str] | None:
        prefix = f"{self.structural_prefix}:"
        if not relation_id.startswith(prefix):
            return None
        parts = relation_id.split(":", maxsplit=2)
        if len(parts) != 3:
            return None
        return parts[1], parts[2]

    def _to_relation_from_issue_context(
        self,
        current_issue_id: str,
        link: Any,
    ) -> Relation | None:
        relation_type = self._match_relation_type(getattr(link, "type", None))
        if relation_type is None:
            return None

        inward_issue = getattr(link, "inwardIssue", None)
        outward_issue = getattr(link, "outwardIssue", None)

        if inward_issue is not None and getattr(inward_issue, "id", None) is not None:
            return Relation(
                id=str(getattr(link, "id", "")) or None,
                source_task_id=str(inward_issue.id),
                target_task_id=current_issue_id,
                relation_type=relation_type,
            )

        if outward_issue is not None and getattr(outward_issue, "id", None) is not None:
            return Relation(
                id=str(getattr(link, "id", "")) or None,
                source_task_id=current_issue_id,
                target_task_id=str(outward_issue.id),
                relation_type=relation_type,
            )

        return None

    def _match_relation_type(self, link_type: Any) -> RelationType | None:
        if link_type is None:
            return None
        candidates = list(self._config.link_mappings)
        if self.uses_custom_contains_links():
            candidates.extend(self._config.contains_link_mappings)
        for mapping in candidates:
            if self._matches_mapping(link_type, mapping):
                return mapping.relation_type
        return None

    def _matches_mapping(self, link_type: Any, mapping: JiraLinkTypeMapping) -> bool:
        if getattr(link_type, "name", None) != mapping.type_name:
            return False
        if mapping.outward_label is None and mapping.inward_label is None:
            return True
        return (
            getattr(link_type, "outward", None) == mapping.outward_label
            and getattr(link_type, "inward", None) == mapping.inward_label
        )
