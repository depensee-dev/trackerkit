from trackerkit.domain.enums import TaskPriority, TaskState, TaskWorkType

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


_PRIORITY_KEYS = {
    TaskPriority.LOW: "minor",
    TaskPriority.MEDIUM: "normal",
    TaskPriority.HIGH: "major",
}

_WORK_TYPE_KEYS = {
    TaskWorkType.BUG: "bug",
    TaskWorkType.FEATURE: "story",
    TaskWorkType.TASK: "task",
    TaskWorkType.REFACTOR: "refactor",
}

_DONE_STATUS_KEYS = frozenset({"closed", "resolved", "done", "cancelled", "canceled"})
_OPEN_STATUS_KEYS = frozenset({"open", "new", "backlog", "reopened"})


def priority_key(value: TaskPriority) -> str:
    return _PRIORITY_KEYS[value]


def work_type_key(value: TaskWorkType) -> str:
    return _WORK_TYPE_KEYS[value]


def status_key_for_state(keys: list[str], state: TaskState) -> str | None:
    """Pick a queue status key that matches the portable state, if one is present."""

    wanted = _DONE_STATUS_KEYS if state is TaskState.DONE else _OPEN_STATUS_KEYS
    for key in keys:
        if key.casefold() in wanted:
            return key
    return None
