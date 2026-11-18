from trackerkit.domain.enums import TaskState

# Stable provider markers for a finished task. Localized status names are not
# included: unknown labels stay open rather than being guessed.
_DONE = frozenset({"done", "closed", "completed", "resolved", "cancelled", "canceled"})


def task_state_for(category: str | None, status_id: str | None = None) -> TaskState | None:
    """Map a provider status to the portable open/done state."""

    if category is None and not status_id:
        return None
    for raw in (category, status_id):
        if raw and raw.strip().casefold() in _DONE:
            return TaskState.DONE
    return TaskState.OPEN
