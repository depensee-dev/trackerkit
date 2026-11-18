from dataclasses import dataclass

from trackerkit.domain.enums import TaskPriority, TaskWorkType
from trackerkit.providers.github.metadata import priority_name, work_type_name

_START_NAMES = ("start date",)
_DUE_NAMES = ("due date", "target date")


@dataclass(frozen=True, slots=True)
class GitHubIssueField:
    id: int
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitHubIssueCatalog:
    type_names: tuple[str, ...] = ()
    priority: GitHubIssueField | None = None
    start_date: GitHubIssueField | None = None
    due_date: GitHubIssueField | None = None

    def type_name(self, work_type: TaskWorkType) -> str | None:
        return _match(self.type_names, work_type_name(work_type))

    def priority_option(self, priority: TaskPriority) -> str | None:
        if self.priority is None:
            return None
        return _match(self.priority.options, priority_name(priority))


def build_catalog(
    issue_types: list[dict],
    issue_fields: list[dict],
) -> GitHubIssueCatalog:
    names: list[str] = []
    for issue_type in issue_types:
        if issue_type.get("is_enabled") is False:
            continue
        name = issue_type.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    by_name = {
        str(field.get("name") or "").strip().casefold(): field
        for field in issue_fields
        if field.get("id") is not None
    }
    return GitHubIssueCatalog(
        type_names=tuple(names),
        priority=_select_field(by_name, ("priority",), "single_select"),
        start_date=_select_field(by_name, _START_NAMES, "date"),
        due_date=_select_field(by_name, _DUE_NAMES, "date"),
    )


def _select_field(
    fields: dict[str, dict],
    names: tuple[str, ...],
    data_type: str,
) -> GitHubIssueField | None:
    for name in names:
        field = fields.get(name)
        if field is None or str(field.get("data_type") or "").casefold() != data_type:
            continue
        options = tuple(
            option["name"]
            for option in field.get("options") or []
            if isinstance(option, dict) and isinstance(option.get("name"), str)
        )
        return GitHubIssueField(id=int(field["id"]), options=options)
    return None


def _match(names: tuple[str, ...], wanted: str) -> str | None:
    folded = wanted.casefold()
    for name in names:
        if name.casefold() == folded:
            return name
    return None
