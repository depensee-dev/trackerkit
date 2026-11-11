import pytest

from trackerkit.domain.enums import RelationType
from trackerkit.domain.errors import ProviderError
from trackerkit.providers.github.identifiers import (
    GitHubTaskHandle,
    build_relation_id,
    parse_relation_id,
)
from trackerkit.providers.github.relations import GitHubRelationPolicy


def test_task_handle_round_trip() -> None:
    handle = GitHubTaskHandle(issue_id=1001, repository_id=200, issue_number=42)
    encoded = str(handle)
    assert encoded == "github:task:v1:1001:200:42"
    assert GitHubTaskHandle.parse(encoded) == handle


@pytest.mark.parametrize(
    "value",
    [
        "1001",
        "github:task:v1:bad:200:42",
        "github:task:v1:1001:200:0",
        "jira:task:v1:1001:200:42",
    ],
)
def test_task_handle_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ProviderError):
        GitHubTaskHandle.parse(value)


@pytest.mark.parametrize("relation_type", list(RelationType))
def test_relation_id_round_trip(relation_type: RelationType) -> None:
    source = "github:task:v1:1001:200:42"
    target = "github:task:v1:1002:200:43"
    relation_id = build_relation_id(source, target, relation_type)
    assert parse_relation_id(relation_id) == (source, target, relation_type)


def test_relates_relation_has_stable_symmetric_identity() -> None:
    policy = GitHubRelationPolicy()
    first = "github:task:v1:1002:200:43"
    second = "github:task:v1:1001:200:42"
    forward = policy.build_relation(first, second, RelationType.RELATES)
    reverse = policy.build_relation(second, first, RelationType.RELATES)
    assert forward == reverse
    assert forward.source_task_id == second
    assert forward.target_task_id == first


def test_parse_relation_id_rejects_malformed_values() -> None:
    with pytest.raises(ProviderError):
        parse_relation_id("github:relation:v1:unknown:first:second")
