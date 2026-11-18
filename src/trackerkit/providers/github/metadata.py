from trackerkit.domain.enums import TaskPriority, TaskState, TaskWorkType

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


_PRIORITY_NAMES = {
    TaskPriority.LOW: "Low",
    TaskPriority.MEDIUM: "Medium",
    TaskPriority.HIGH: "High",
}

_WORK_TYPE_NAMES = {
    TaskWorkType.BUG: "Bug",
    TaskWorkType.FEATURE: "Feature",
    TaskWorkType.TASK: "Task",
    TaskWorkType.REFACTOR: "Refactor",
}


def priority_name(value: TaskPriority) -> str:
    return _PRIORITY_NAMES[value]


def work_type_name(value: TaskWorkType) -> str:
    return _WORK_TYPE_NAMES[value]


def issue_state(state: TaskState | None, status_id: str | None) -> str | None:
    if state is TaskState.DONE:
        return "closed"
    if state is TaskState.OPEN:
        return "open"
    return status_id
