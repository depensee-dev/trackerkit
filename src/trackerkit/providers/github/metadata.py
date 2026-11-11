from trackerkit.domain.enums import TaskPriority, TaskWorkType

_PRIORITIES = {
    "low": TaskPriority.LOW,
    "medium": TaskPriority.MEDIUM,
    "high": TaskPriority.HIGH,
}

_WORK_TYPES = {
    "bug": TaskWorkType.BUG,
    "feature": TaskWorkType.FEATURE,
    "task": TaskWorkType.TASK,
    "refactor": TaskWorkType.REFACTOR,
}


def normalize_priority(value: str | None) -> TaskPriority | None:
    if value is None:
        return None
    return _PRIORITIES.get(value.strip().casefold())


def normalize_work_type(value: str | None) -> TaskWorkType | None:
    if value is None:
        return None
    return _WORK_TYPES.get(value.strip().casefold())
