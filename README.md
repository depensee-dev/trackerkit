# trackerkit

Unified async client library for Jira, Yandex Tracker, and GitHub integrations.

## Status
- early-stage internal library;
- API and provider coverage may still evolve;
- actively developed against a shared contract for Jira, Yandex Tracker, and GitHub.

### Asana removal

Asana was removed in `0.4.0`, including the adapter and runtime dependency.
Applications that still need it should use `trackerkit>=0.3.0,<0.4.0`.

## Installation

Install from PyPI:

```bash
pip install trackerkit
```

Install from a Git tag:

```bash
pip install "git+https://github.com/depensee-dev/trackerkit.git@v0.4.0"
```

Install from the `main` branch:

```bash
pip install "git+https://github.com/depensee-dev/trackerkit.git@main"
```

## Local development

```bash
poetry install
```

Install from the current project directory:

```bash
pip install .
```

## Goals
- provide one common contract for supported task trackers;
- hide provider-specific SDK and HTTP details from the main backend;
- expose only shared entities and operations;
- keep the design extensible and testable.

## Supported providers
- Jira
- Yandex Tracker
- GitHub (Issues and repository-backed projects)

## Current scope
- one facade client per one selected task tracker;
- common async client contract;
- shared models for tasks, projects, users, comments, relations, and statuses;
- provider auth configs;
- real provider adapters for `workspaces`, `projects`, and `tasks`;
- relation CRUD for all three providers;
- users and comments are modeled in the shared contract, but provider adapters currently report them as unsupported capabilities;
- client factory and explicit HTTP resource cleanup.

GitHub supports issue create/update but not direct issue deletion through this adapter.
GitHub project write operations (repository create/update/delete) currently raise
`ProviderCapabilityError`.

## Internal architecture
- capability-based contracts instead of one monolithic provider interface;
- `TrackerClient` facade with centralized connection guard;
- provider adapters split into `transport`, `queries`, `mappers`, and `errors`;
- domain models and auth configs remain typed with `Pydantic`;
- the public API stays async even when a provider transport uses a sync SDK under the hood;
- GitHub uses native async REST via `httpx`, including the current sub-issue,
  dependency, and related-issue endpoints.

## Package layout
```text
docs/
examples/
src/
└── trackerkit/
    ├── contracts/
    ├── domain/
    ├── factory/
    ├── providers/
    ├── tracker_client.py
    └── __init__.py
```

## Usage
```python
from trackerkit import TrackerClient

async with TrackerClient(
    provider="github",
    auth_data={"access_token": "secret"},
    connection_timeout=3,
) as client:
    projects = await client.list_projects()
```

`GitHubAuthConfig` also accepts `base_url`, `api_version`, and `max_concurrency`.
The defaults target GitHub.com with API version `2026-03-10`.

## Development
- Python `3.12+` (required — the codebase uses `from datetime import UTC` and
  modern `X | Y` generics that need 3.10+ at minimum, and `UTC` since 3.11;
  3.12 is the chosen lower bound to match `pydantic 2.12` and `ruff` defaults)
- package manager: `poetry`
- import root: `src`

### Local checks
Build the package locally:

```bash
python -m pip wheel . --no-deps
```

Lint and tests (after `poetry install`):

```bash
poetry run ruff check
poetry run ruff format --check
poetry run pytest
```

## Service integration
This library is designed to be embedded into a backend service.

- the primary configuration path is explicit `TrackerClient` initialization;
- the service loads configuration and passes typed `auth_data` into `TrackerClient`;
- optional helpers such as `RelationMappingConfig.from_env()` read environment variables only when the host service or an example calls them explicitly;
- connection behavior is configured via explicit `TrackerClient` arguments instead of `auth_data`;
- provider-specific connection options such as GitHub `max_concurrency` live in `auth_data`;
- only `examples/` load local env files for manual development checks;
- close the facade with `close()` or `async with` so GitHub HTTP connections are released.

### Pydantic settings example
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

from trackerkit import TrackerClient


class GitHubSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    token: str


settings = GitHubSettings()

client = TrackerClient(
    provider="github",
    auth_data={"access_token": settings.token},
    connection_timeout=3,
)
```

## Documentation
- `docs/auth.md` - authorization, client initialization, and lifecycle.
- `docs/projects.md` - workspaces and project methods.
- `docs/tasks.md` - task methods and task models.
- `docs/relations.md` - relation semantics, mapping config, and CRUD behavior.
- `ROADMAP.md` - status and priorities driven by the host product (Depensee).
- `TECH_ROADMAP.md` - engineering debt, tests, and execution order.
- `THIRD_PARTY_LICENSES.md` - direct runtime dependency license summary.

## Examples
- `examples/jira_example.py` - Jira auth, projects flow, task flow, and relation flow.
- `examples/yandex_example.py` - Yandex Tracker auth, projects flow, task flow, and relation flow.
- `examples/github_example.py` - read-only GitHub auth, repository issue, and relation inspection. Requires `GITHUB_REPOSITORY`; never modifies GitHub data.

## Notes
`src` is configured as the import root for the repository.

`Jira`, `Yandex Tracker`, and `GitHub` implement the shared `workspaces`,
`projects`, and `tasks` contract, subject to the documented capability limits.
All three implement relation CRUD for the core product relation types.

## Entity Mapping
`trackerkit` exposes a canonical task-tracker model.
This model is grounded in provider documentation first, then normalized into a shared contract for the backend.
Shared entities do not have to match provider-native names one to one.
They are mapped by functional role in the workflow, and some shared entities are integration-level abstractions rather than native provider objects.

### Provider source model
| Shared entity | Jira source model | Yandex Tracker source model | GitHub source model |
| --- | --- | --- | --- |
| `Workspace` | integration-level container for one Jira site / instance | organization context selected by `X-Org-ID` or `X-Cloud-Org-ID` | user account or organization that owns repositories |
| `Project` | native Jira project | queue for operational task work; Yandex also has a separate native `project` entity above queues | repository; not a GitHub Projects board |
| `Task` | native Jira issue / work item | native Yandex issue in a queue | native GitHub issue, excluding pull requests |
| `Status` | native issue status | native issue status in queue workflow | issue state: `open` or `closed` |
| `User` | native Jira user | native Tracker user | GitHub user identified by login |
| `Relation` | native Jira issue link or hierarchy relation depending on config | native issue link with explicit relationship type and direction | related issue, issue dependency, or parent/sub-issue hierarchy |

### Canonical mapping decision in `trackerkit`
- `Jira`: shared `Project` maps to Jira project, and shared `Task` maps to issue.
- `Yandex Tracker`: shared `Project` maps to queue, and shared `Task` maps to issue inside that queue.
- `Yandex Tracker`: native Yandex `project` is documented as a separate higher-level entity and is not part of the current shared contract.
- `Yandex Tracker`: direct issue deletion is unsupported by the adapter; close/archive semantics remain provider-specific.
- `GitHub`: shared `Project` maps to repository because an issue belongs to exactly one repository. GitHub Projects has many-to-many membership and is not equivalent.
- `GitHub`: shared `Task` maps to issue. Task IDs are opaque versioned handles containing the global issue ID, repository ID, and issue number; display keys use `owner/repo#number`.
- `GitHub`: direct issue deletion and repository write operations are unsupported by the current adapter.
- `Jira`: shared `Relation` maps to issue links for `relates` and `blocks`, and to hierarchy for default `contains`.
- `Yandex Tracker`: shared `Relation` maps to native issue links; provider-native link types cover both dependency-style and hierarchy-style relations.
- `GitHub`: shared `Relation` maps to native related issues, dependencies, and sub-issues.

### Product-first core relation semantics
For the product concept, the most important relation taxonomy is the one that supports canvas visualization and planning semantics.
The core visual set is smaller than the full set of provider-native link types.

| Core relation | Meaning in the product | Default visual style | Jira source model | Yandex Tracker source model | GitHub source model |
| --- | --- | --- | --- | --- | --- |
| `relates` | weak semantic connection without strict dependency | dashed line | symmetric relates-style issue link when configured | native `relates` | native `relates_to` |
| `blocks` | one task blocks or unlocks another | directed arrow | Blocks-style issue link direction | `depends on` / `is dependent by` | `blocked by` / `blocking` |
| `contains` | one task structurally includes, decomposes, or parents another | solid line | work item hierarchy such as parent-child or subtask hierarchy | `is parent task for` / `is subtask for`, plus epic-style hierarchy when relevant | parent issue / sub-issues |

### Non-core provider relations
Provider-specific relation variants such as duplicates, clones, epics, or custom hierarchy
levels are not part of the public `RelationType` enum. They can be handled later as
provider metadata or normalized into one of the three core relation types when that
preserves the product meaning.

### Integration note
- The product-facing taxonomy above is the active shared model for relation work in the library.
- Jira allows custom issue link types, so label-based normalization stays explicit and source-aware.
- `RelationMappingConfig` provides a default `Mode A` structural hierarchy for Jira `contains` and leaves room for `Mode B` custom link mapping.
- GitHub needs no relation-label mapping because its native relation types have stable semantics.

### Sources
- Jira: [Projects / spaces overview](https://www.atlassian.com/software/jira/guides/projects/overview)
- Jira: [Issue linking model](https://developer.atlassian.com/cloud/jira/platform/issue-linking-model/)
- Yandex Tracker: [Queue introduction](https://yandex.ru/support/tracker/en/queue-intro)
- Yandex Tracker: [Get project parameters](https://yandex.ru/support/tracker/en/api-ref/projects/get-project)
- Yandex Tracker: [Linking issues](https://yandex.ru/support/tracker/en/api-ref/issues/link-issue)
- GitHub: [Issues REST API](https://docs.github.com/en/rest/issues/issues)
- GitHub: [Sub-issues REST API](https://docs.github.com/en/rest/issues/sub-issues)
- GitHub: [Issue dependencies REST API](https://docs.github.com/en/rest/issues/issue-dependencies)
- GitHub: [Repositories REST API](https://docs.github.com/en/rest/repos/repos)

Examples use environment variables instead of hardcoded credentials.
Host services should prefer explicit settings objects and pass `auth_data` / `relation_mapping`
into `TrackerClient` during initialization:
- `JIRA_BASE_URL`
- `JIRA_TOKEN`
- `JIRA_RELATES_LINK_TYPES` - optional Jira relation mapping, `Type` or `Type|outward|inward`
- `JIRA_BLOCKS_LINK_TYPES` - optional Jira relation mapping, `Type` or `Type|outward|inward`
- `JIRA_CONTAINS_LINK_TYPES` - optional Jira relation mapping for custom `contains`
- `JIRA_CONTAINS_MODE` - optional Jira contains mode override
- `YANDEX_TOKEN`
- `YANDEX_CLOUD_ORG_ID` - use one of `YANDEX_CLOUD_ORG_ID` or `YANDEX_ORG_ID`
- `YANDEX_ORG_ID` - use one of `YANDEX_CLOUD_ORG_ID` or `YANDEX_ORG_ID`
- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY` - required by the live example, `owner/repository`
- `GITHUB_API_URL` - optional, defaults to `https://api.github.com`
- `GITHUB_API_VERSION` - optional, defaults to `2026-03-10`

Local development files:
- `.env.example` - fallback template for local example runs
- `.env` - local override for real local credentials

Examples load variables with this priority:
1. process environment
2. `.env`
3. `.env.example`

## Roadmap
See `ROADMAP.md` for the feature plan (next: real-time sync; later: CPM / PERT data, scale and auth) and `TECH_ROADMAP.md` for engineering tasks.
