# Tasks

## Methods
```python
await client.get_task(task_id: str) -> Task
await client.list_tasks(query: TaskQuery | None = None) -> list[Task]
await client.count_tasks(query: TaskQuery | None = None) -> int
await client.create_task(payload: CreateTaskInput) -> Task
await client.update_task(task_id: str, payload: UpdateTaskInput) -> Task
await client.delete_task(task_id: str) -> None
```

## Models

### Task
- `id`: `str`
- `key`: `str | None`
- `title`: `str`
- `description`: `str | None`
- `project_id`: `str | None`
- `status`: `Status | None`
- `priority`: `TaskPriority | None` — `low`, `medium`, or `high`
- `work_type`: `TaskWorkType | None` — `bug`, `feature`, `task`, or `refactor`
- `assignee`: `User | None`
- `reporter`: `User | None`
- `created_at`: `datetime | None`
- `updated_at`: `datetime | None`
- `due_date`: `datetime | None`
- `url`: `str | None`

### TaskQuery
- `project_id`: `str | None`
- `assignee_id`: `str | None`
- `status_id`: `str | None`
- `updated_since`: `datetime | None`
- `limit`: `int | None` — soft cap on materialized rows; honored by GitHub, ignored by Jira/Yandex because their server queries are already bounded. GitHub fetches all matching issues when omitted.

### CreateTaskInput
- `title`: `str`
- `description`: `str | None`
- `project_id`: `str | None`
- `assignee_id`: `str | None`
- `status_id`: `str | None`
- `due_date`: `datetime | None`

### UpdateTaskInput
- `title`: `str | None`
- `description`: `str | None`
- `assignee_id`: `str | None`
- `status_id`: `str | None`
- `due_date`: `datetime | None`

## Notes
- `get_task()` returns one task by provider-specific identifier.
- `list_tasks()` supports a common query model only.
- provider-specific fields are intentionally excluded from the shared contract.
- `Jira`, `Yandex Tracker`, and `GitHub` implement this section subject to documented capability limits.
- In `GitHub`, `list_tasks()`, `count_tasks()`, and `create_task()` require `TaskQuery.project_id` / `CreateTaskInput.project_id`. This avoids an unbounded scan across every accessible repository.
- In `Yandex Tracker`, unified `Task` maps to issue, and `Task.project_id` maps to queue key.
- In `Yandex Tracker`, direct issue deletion is unsupported by the adapter.
- Some status transitions depend on provider-specific rules and permissions.
- The public library API is async, while some provider transports may wrap sync SDKs internally.

## Canonical priority and work type

The shared fields are optional. Each provider has an explicit mapping table;
unknown values return `None` and are never inferred from aliases or localized
labels.

| Canonical value | Jira | Yandex Tracker (stable keys) | GitHub |
| --- | --- | --- | --- |
| `priority=low` | `Lowest`, `Low` | `trivial`, `minor` | `Low` |
| `priority=medium` | `Medium` | `normal` | `Medium` |
| `priority=high` | `High`, `Highest` | `major`, `critical`, `blocker` | `High` |
| `work_type=bug` | `Bug` | `bug` | `Bug` |
| `work_type=feature` | `Story` | `story`, `improvement`, `newFeature` | `Feature` |
| `work_type=task` | `Task`, `Sub-task` | `task`, `subtask` | `Task` |
| `work_type=refactor` | `Refactor`, `Refactoring` | `refactor`, `refactoring` | `Refactor` |

Jira reads `priority.name` and `issuetype.name`. Yandex reads the `key` of its
priority/type objects, so localization of `display` does not affect mapping.
GitHub reads native `type.name` and the single-select issue field named exactly
`Priority` (case-insensitive) from `issue_field_values`. Other GitHub fields,
including `Effort`, are not mapped to these properties.

## GitHub Mapping and Limits
- `Task` maps to an issue inside a repository; pull requests returned by Issues endpoints are excluded.
- `Task.id` is an opaque, versioned handle containing global issue ID, repository ID, and issue number. Do not parse or construct it in host code.
- `Task.key` is `owner/repository#number`.
- `Task.project_id` is the numeric repository ID.
- `title`, `description`, `assignee`, `reporter`, timestamps, and `url` map to `title`, `body`, `assignee`, `user`, `created_at` / `updated_at`, and `html_url`.
- `User.id` is the GitHub login because issue filters and assignee writes accept logins.
- Only `open` and `closed` status IDs are supported. Categories are `todo` and `done` respectively. GitHub Projects status fields are not issue workflow states and are not mapped.
- GitHub issues have no native per-issue due date. Passing `due_date` raises `ProviderCapabilityError`; milestone due dates are not substituted.
- Creating a closed issue is implemented as create followed by close.
- Updating `assignee_id` sends a one-element `assignees` list and therefore replaces the existing assignee set, consistent with the canonical single-assignee model.
- Multiple assignees are otherwise collapsed to the first provider `assignee` on read.
- `delete_task()` is unsupported; closing an issue is not treated as deletion.
- GitHub relation reads use several native endpoints per issue. The transport limits concurrency per client, and callers should avoid unbounded fan-out across large repositories.

## Provider Mapping
| Shared entity | Jira | Yandex Tracker | GitHub |
| --- | --- | --- | --- |
| `Task` | issue / work item | issue inside queue | issue inside repository |
| `Status` | workflow status | queue workflow status | `open` / `closed` state |
| `User.id` | account ID | provider user ID / login | login |

## Entity Relationship
- `Task.project_id` points to the parent `Project`.
- In `Yandex Tracker`, this means each task belongs to a queue represented by unified `Project`.
- In `GitHub`, each issue belongs to a repository represented by unified `Project`.

## Relation Mapping
`Relation` is a shared task-to-task edge in the canonical model.
The detailed CRUD contract and provider-specific mapping rules live in `docs/relations.md`.

| Shared relation | Jira | Yandex Tracker | GitHub |
| --- | --- | --- | --- |
| `relates` | configurable relates-style issue link | native `relates` | native `relates_to` |
| `blocks` | Blocks-style issue link | `depends on` / `is dependent by` | `blocked by` / `blocking` |
| `contains` | parent-child or subtask hierarchy | parent/subtask link | parent issue / sub-issues |

## Sources
- Jira: [Issue linking model](https://developer.atlassian.com/cloud/jira/platform/issue-linking-model/)
- Jira: [Configure the work type hierarchy](https://support.atlassian.com/jira-cloud-administration/docs/configure-the-issue-type-hierarchy/)
- Yandex Tracker: [Linking issues](https://yandex.ru/support/tracker/en/api-ref/issues/link-issue)
- GitHub: [Issues REST API](https://docs.github.com/en/rest/issues/issues)
- GitHub: [Sub-issues REST API](https://docs.github.com/en/rest/issues/sub-issues)
- GitHub: [Issue dependencies REST API](https://docs.github.com/en/rest/issues/issue-dependencies)

## Example
```python
from trackerkit import CreateTaskInput, TaskQuery, TrackerClient, UpdateTaskInput

async with TrackerClient(
    provider="github",
    auth_data={"access_token": "secret"},
) as client:
    tasks = await client.list_tasks(TaskQuery(project_id="123456789"))

    created = await client.create_task(
        CreateTaskInput(
            title="Prepare release notes",
            description="Draft the release notes for sprint 12",
            project_id="123456789",
        )
    )

    fetched = await client.get_task(created.id)
    updated = await client.update_task(
        fetched.id,
        UpdateTaskInput(description="Updated release notes draft"),
    )
```
