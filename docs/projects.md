# Projects

## Methods
```python
await client.list_workspaces() -> list[Workspace]
await client.get_project(project_id: str) -> Project
await client.list_projects(workspace_id: str | None = None) -> list[Project]
await client.create_project(payload: CreateProjectInput) -> Project
await client.update_project(project_id: str, payload: UpdateProjectInput) -> Project
await client.delete_project(project_id: str) -> None
```

## Models

### Workspace
- `id`: `str`
- `name`: `str`
- `key`: `str | None`

#### Workspace.id by provider
- `Jira`: synthetic value of the form `jira:<host>` (e.g. `jira:your-domain.atlassian.net`). This is not a Jira API endpoint; treat it as an opaque identifier for routing in your service.
- `Yandex Tracker`: organization id (`cloud_org_id` or `org_id`) or the literal `yandex-tracker`.
- `GitHub`: `github:user:<id>` for a user account or `github:org:<id>` for an organization. `Workspace.key` is the account login.

### Project
- `id`: `str`
- `name`: `str`
- `key`: `str | None`
- `description`: `str | None`
- `workspace_id`: `str | None`

### CreateProjectInput
- `name`: `str`
- `key`: `str | None`
- `description`: `str | None`
- `workspace_id`: `str | None`

### UpdateProjectInput
- `name`: `str | None`
- `key`: `str | None`
- `description`: `str | None`

## Notes
- `Workspace` is a top-level container above projects.
- `workspace_id` in `list_projects()` can be omitted.
- provider-specific limitations raise `ProviderCapabilityError`.
- `Jira`, `Yandex Tracker`, and `GitHub` implement workspace and project reads.
- In `Yandex Tracker`, official documentation distinguishes `queue` and native `project` as separate entities.
- In `Yandex Tracker`, every issue belongs to a queue, while native `project` is a higher-level entity that can include queues.
- In `trackerkit`, shared `Project` is mapped to the provider entity that acts as the main operational task container.
- For `Yandex Tracker`, this means shared `Project` is mapped to `queue`; project writes create, update, and delete queues.
- For `GitHub`, shared `Project` is mapped to a repository. `Project.id` is the stable numeric repository ID, while `Project.key` is `owner/repository`.
- `GitHub.list_projects()` lists repositories visible to the user token, including owned, collaborator, and organization-member repositories.
- GitHub project create/update/delete operations would mutate repositories and are intentionally unsupported in the current adapter.
- The public library API is async, while some provider transports may wrap sync SDKs internally.

## Canonical Mapping
The shared `Project` model represents the main operational container for tasks in each provider.
This is a canonical integration decision made on top of provider source models, not a claim that provider-native names are identical.

| Shared entity | Jira | Yandex Tracker | GitHub |
| --- | --- | --- | --- |
| `Workspace` | integration-level container for one Jira site / instance | organization context | user account or organization |
| `Project` | Jira project | queue | repository |

### Provider notes
- `Jira`: `Project` maps to Jira project.
- `Yandex Tracker`: `Project` maps to queue, not to the native Yandex Tracker `project` entity.
- `GitHub`: `Project` maps to repository, not GitHub Projects. A GitHub issue has exactly one repository but may be added to multiple GitHub Projects boards.

## Sources
- Jira: [Projects / spaces overview](https://www.atlassian.com/software/jira/guides/projects/overview)
- Yandex Tracker: [Queue introduction](https://yandex.ru/support/tracker/en/queue-intro)
- Yandex Tracker: [Get project parameters](https://yandex.ru/support/tracker/en/api-ref/projects/get-project)
- GitHub: [Repositories REST API](https://docs.github.com/en/rest/repos/repos)

## Entity Relationship
- `Workspace` contains many `Project`.
- `Project` contains many `Task`.
- In `Yandex Tracker`: organization/workspace -> queue -> issues.
- In `GitHub`: user or organization -> repository -> issues.

## Example
```python
from trackerkit import TrackerClient

async with TrackerClient(
    provider="github",
    auth_data={"access_token": "secret"},
) as client:
    workspaces = await client.list_workspaces()
    projects = await client.list_projects()
    project = await client.get_project(projects[0].id)
```
