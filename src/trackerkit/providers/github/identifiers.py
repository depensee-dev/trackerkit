import base64
from dataclasses import dataclass

from trackerkit.domain.enums import RelationType
from trackerkit.domain.errors import ProviderError

_TASK_PREFIX = "github:task:v1"
_RELATION_PREFIX = "github:relation:v1"


@dataclass(frozen=True)
class GitHubTaskHandle:
    issue_id: int
    repository_id: int
    issue_number: int

    def __str__(self) -> str:
        return f"{_TASK_PREFIX}:{self.issue_id}:{self.repository_id}:{self.issue_number}"

    @classmethod
    def parse(cls, value: str) -> "GitHubTaskHandle":
        parts = value.split(":")
        if len(parts) != 6 or ":".join(parts[:3]) != _TASK_PREFIX:
            raise ProviderError(f"Invalid GitHub task id: {value!r}")
        try:
            issue_id, repository_id, issue_number = (int(part) for part in parts[3:])
        except ValueError as error:
            raise ProviderError(f"Invalid GitHub task id: {value!r}") from error
        if min(issue_id, repository_id, issue_number) <= 0:
            raise ProviderError(f"Invalid GitHub task id: {value!r}")
        return cls(
            issue_id=issue_id,
            repository_id=repository_id,
            issue_number=issue_number,
        )


def encode_relation_part(value: str) -> str:
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_relation_part(value: str) -> str:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise ProviderError("Invalid GitHub relation id.") from error


def build_relation_id(
    source_task_id: str,
    target_task_id: str,
    relation_type: RelationType,
) -> str:
    return (
        f"{_RELATION_PREFIX}:{relation_type.value}:"
        f"{encode_relation_part(source_task_id)}:{encode_relation_part(target_task_id)}"
    )


def parse_relation_id(value: str) -> tuple[str, str, RelationType]:
    parts = value.split(":")
    if len(parts) != 6 or ":".join(parts[:3]) != _RELATION_PREFIX:
        raise ProviderError(f"Invalid GitHub relation id: {value!r}")
    try:
        relation_type = RelationType(parts[3])
    except ValueError as error:
        raise ProviderError(f"Invalid GitHub relation id: {value!r}") from error
    source_task_id = decode_relation_part(parts[4])
    target_task_id = decode_relation_part(parts[5])
    GitHubTaskHandle.parse(source_task_id)
    GitHubTaskHandle.parse(target_task_id)
    return source_task_id, target_task_id, relation_type
