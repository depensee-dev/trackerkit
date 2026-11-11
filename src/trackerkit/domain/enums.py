from enum import Enum


class Provider(str, Enum):
    JIRA = "jira"
    YANDEX_TRACKER = "yandex_tracker"
    GITHUB = "github"


class RelationType(str, Enum):
    RELATES = "relates"
    BLOCKS = "blocks"
    CONTAINS = "contains"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskWorkType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    TASK = "task"
    REFACTOR = "refactor"


class ConnectionErrorKind(str, Enum):
    """Stable taxonomy of connection-check failure reasons.

    `ConnectionDiagnostic.error_kind` uses these values; the string base
    keeps backward compatibility with callers that compare against literals
    like ``"authentication"``.
    """

    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    CAPABILITY = "capability"
    PROVIDER = "provider"
