from trackerkit.contracts.comments import CommentCapability
from trackerkit.contracts.connection import ConnectionCapability
from trackerkit.contracts.projects import (
    ProjectReadCapability,
    ProjectWriteCapability,
    WorkspaceCapability,
)
from trackerkit.contracts.relations import RelationCapability
from trackerkit.contracts.tasks import TaskReadCapability, TaskWriteCapability
from trackerkit.contracts.users import UserCapability


class TaskTrackerClient(
    ConnectionCapability,
    TaskReadCapability,
    TaskWriteCapability,
    WorkspaceCapability,
    ProjectReadCapability,
    ProjectWriteCapability,
    UserCapability,
    CommentCapability,
    RelationCapability,
):
    """Unified async port composed from small capability contracts."""

