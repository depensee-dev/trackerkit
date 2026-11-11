from trackerkit.domain.enums import TaskPriority, TaskWorkType

_PRIORITIES = {
    "trivial": TaskPriority.LOW,
    "minor": TaskPriority.LOW,
    "normal": TaskPriority.MEDIUM,
    "major": TaskPriority.HIGH,
    "critical": TaskPriority.HIGH,
    "blocker": TaskPriority.HIGH,
}

_WORK_TYPES = {
    "bug": TaskWorkType.BUG,
    "story": TaskWorkType.FEATURE,
    "improvement": TaskWorkType.FEATURE,
    "newfeature": TaskWorkType.FEATURE,
    "task": TaskWorkType.TASK,
    "subtask": TaskWorkType.TASK,
    "refactor": TaskWorkType.REFACTOR,
    "refactoring": TaskWorkType.REFACTOR,
}


def normalize_priority(value: str | None) -> TaskPriority | None:
    if value is None:
        return None
    return _PRIORITIES.get(value.strip().casefold())


def normalize_work_type(value: str | None) -> TaskWorkType | None:
    if value is None:
        return None
    return _WORK_TYPES.get(value.strip().casefold())
