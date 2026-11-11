from trackerkit.domain.enums import RelationType
from trackerkit.domain.models import Relation
from trackerkit.providers.github.identifiers import (
    GitHubTaskHandle,
    build_relation_id,
    parse_relation_id,
)


class GitHubRelationPolicy:
    def build_relation(
        self,
        source_task_id: str,
        target_task_id: str,
        relation_type: RelationType,
    ) -> Relation:
        if relation_type is RelationType.RELATES:
            source = GitHubTaskHandle.parse(source_task_id)
            target = GitHubTaskHandle.parse(target_task_id)
            if source.issue_id > target.issue_id:
                source_task_id, target_task_id = target_task_id, source_task_id
        return Relation(
            id=build_relation_id(source_task_id, target_task_id, relation_type),
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            relation_type=relation_type,
        )

    def parse_relation_id(self, relation_id: str) -> Relation:
        source_task_id, target_task_id, relation_type = parse_relation_id(relation_id)
        return Relation(
            id=relation_id,
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            relation_type=relation_type,
        )
