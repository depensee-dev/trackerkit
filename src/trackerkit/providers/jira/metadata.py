from trackerkit.domain.enums import TaskPriority, TaskState, TaskWorkType

_PRIORITIES = {
    "lowest": TaskPriority.LOW,
    "low": TaskPriority.LOW,
    "medium": TaskPriority.MEDIUM,
    "high": TaskPriority.HIGH,
    "highest": TaskPriority.HIGH,
}

_WORK_TYPES = {
    "bug": TaskWorkType.BUG,
    "story": TaskWorkType.FEATURE,
    "task": TaskWorkType.TASK,
    "sub-task": TaskWorkType.TASK,
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


_PRIORITY_NAMES = {
    TaskPriority.LOW: "Low",
    TaskPriority.MEDIUM: "Medium",
    TaskPriority.HIGH: "High",
}

_WORK_TYPE_NAMES = {
    TaskWorkType.BUG: "Bug",
    TaskWorkType.FEATURE: "Story",
    TaskWorkType.TASK: "Task",
    TaskWorkType.REFACTOR: "Refactor",
}


def priority_name(value: TaskPriority) -> str:
    return _PRIORITY_NAMES[value]


def work_type_name(value: TaskWorkType) -> str:
    return _WORK_TYPE_NAMES[value]


def select_transition_id(transitions: list[dict], state: TaskState) -> str | None:
    """Pick a Jira transition id that lands in the portable state."""

    def category(item: dict) -> str:
        destination = item.get("to") or {}
        status_category = destination.get("statusCategory") or {}
        return str(status_category.get("key") or "").casefold()

    preferred = {"done"} if state is TaskState.DONE else {"new"}
    for item in transitions:
        if category(item) in preferred and item.get("id"):
            return str(item["id"])
    if state is TaskState.OPEN:
        for item in transitions:
            if category(item) not in {"", "done"} and item.get("id"):
                return str(item["id"])
    return None
