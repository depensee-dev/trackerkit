# trackerkit

Unified async client library for Jira, Yandex Tracker, and Asana integrations.

## Status
- early-stage internal library;
- API and provider coverage may still evolve;
- currently focused on a shared contract for Jira, Yandex Tracker, and Asana.

## Installation

Install from PyPI:

```bash
pip install trackerkit
```

Install from a Git tag:

```bash
pip install "git+https://github.com/depensee-dev/trackerkit.git@v0.2.0"
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
- hide provider-specific SDK details from the main backend;
- expose only shared entities and operations;
- keep the design extensible and testable.

## Supported providers
- Jira
- Yandex Tracker
- Asana

## Current scope
- one facade client per one selected task tracker;
- common async client contract;
- shared models for tasks, projects, users, comments, relations, and statuses;
- provider auth configs;
- real provider adapters for `workspaces`, `projects`, and `tasks`;
- relation CRUD for `Jira` and `Yandex Tracker`;
- users and comments are modeled in the shared contract, but provider adapters currently report them as unsupported capabilities;
- client factory.

## Internal architecture
- capability-based contracts instead of one monolithic provider interface;
- `TrackerClient` facade with centralized connection guard;
- provider adapters split into `transport`, `queries`, `mappers`, and `errors`;
- domain models and auth configs remain typed with `Pydantic`;
- the public API stays async even when a provider transport uses a sync SDK under the hood.

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

client = TrackerClient(
    provider="jira",
    auth_data={
        "base_url": "https://your-domain.atlassian.net",
        "access_token": "secret",
    },
    connection_timeout=3,
    max_retries=0,
)
```

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
- only `examples/` load local env files for manual development checks.

### Pydantic settings example
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

from trackerkit import TrackerClient


class JiraSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    base_url: str
    token: str


settings = JiraSettings()

client = TrackerClient(
    provider="jira",
    auth_data={
        "base_url": settings.base_url,
        "access_token": settings.token,
    },
    connection_timeout=3,
    max_retries=0,
)
```

## Documentation
- `docs/auth.md` - authorization and client initialization.
- `docs/projects.md` - workspaces and project methods.
- `docs/tasks.md` - task methods and task models.
- `docs/relations.md` - relation semantics, mapping config, and CRUD behavior.
- `ROADMAP.md` - current status, planned work, and future provider candidates.
- `THIRD_PARTY_LICENSES.md` - direct runtime dependency license summary.

## Examples
- `examples/jira_example.py` - Jira auth, projects flow, task flow, and relation flow.
- `examples/yandex_example.py` - Yandex Tracker auth, projects flow, task flow, and relation flow.
- `examples/asana_example.py` - Asana auth and readonly inspection flow.

## Notes
`src` is configured as the import root for the repository.

`Jira`, `Yandex Tracker`, and `Asana` already implement the shared `workspaces`, `projects`, and `tasks` contract. `Jira` and `Yandex Tracker` also implement relation CRUD for the core product relation types. `Asana` relations remain follow-up work.

## Entity Mapping
`trackerkit` exposes a canonical task-tracker model.
This model is grounded in provider documentation first, then normalized into a shared contract for the backend.
Shared entities do not have to match provider-native names one to one.
They are mapped by functional role in the workflow, and some shared entities are integration-level abstractions rather than native provider objects.

### Provider source model
| Shared entity | Jira source model | Yandex Tracker source model | Asana source model |
| --- | --- | --- | --- |
| `Workspace` | integration-level container for one Jira site / instance | organization context selected by `X-Org-ID` or `X-Cloud-Org-ID` | native Asana workspace |
| `Project` | native Jira project | queue for operational task work; Yandex also has a separate native `project` entity above queues | native Asana project |
| `Task` | native Jira issue / work item | native Yandex issue in a queue | native Asana task |
| `Status` | native issue status | native issue status in queue workflow | task completion state and related task state fields |
| `User` | native Jira user | native Tracker user | native Asana user |
| `Relation` | native Jira issue link or hierarchy relation depending on config | native issue link with explicit relationship type and direction | task dependency / dependent edge rather than a general-purpose typed link |

### Canonical mapping decision in `trackerkit`
- `Jira`: shared `Project` maps to Jira project, and shared `Task` maps to issue.
- `Yandex Tracker`: shared `Project` maps to queue, and shared `Task` maps to issue inside that queue.
- `Yandex Tracker`: native Yandex `project` is documented as a separate higher-level entity and is not part of the current shared contract.
- `Yandex Tracker`: direct issue deletion is not supported by the provider in the same way as in some other trackers, so task deletion should be modeled as unsupported or as a separate close/archive workflow.
- `Asana`: shared `Project` maps to Asana project, and shared `Task` maps to task.
- `Jira`: shared `Relation` maps to issue links for `relates` and `blocks`, and to hierarchy for default `contains`.
- `Yandex Tracker`: shared `Relation` maps to native issue links; provider-native link types cover both dependency-style and hierarchy-style relations.
- `Asana`: relation mapping is conceptually clear for dependencies and subtasks, but relation CRUD is not implemented in the adapter yet.

### Product-first core relation semantics
For the product concept, the most important relation taxonomy is the one that supports canvas visualization and planning semantics.
The core visual set is smaller than the full set of provider-native link types.

| Core relation | Meaning in the product | Default visual style | Jira source model | Yandex Tracker source model | Asana source model |
| --- | --- | --- | --- | --- | --- |
| `relates` | weak semantic connection without strict dependency | dashed line | symmetric relates-style issue link when configured | native `relates` | no direct native equivalent |
| `blocks` | one task blocks or unlocks another | directed arrow | Blocks-style issue link direction | `depends on` / `is dependent by` | dependencies / dependents |
| `contains` | one task structurally includes, decomposes, or parents another | solid line | work item hierarchy such as parent-child or subtask hierarchy | `is parent task for` / `is subtask for`, plus epic-style hierarchy when relevant | subtasks |

### Non-core provider relations
Provider-specific relation variants such as duplicates, clones, epics, or custom hierarchy
levels are not part of the public `RelationType` enum. They can be handled later as
provider metadata or normalized into one of the three core relation types when that
preserves the product meaning.

### Integration note
- The product-facing taxonomy above is the active shared model for relation work in the library.
- Jira allows custom issue link types, so label-based normalization stays explicit and source-aware.
- `RelationMappingConfig` provides a default `Mode A` structural hierarchy for Jira `contains` and leaves room for `Mode B` custom link mapping.
- Asana covers dependency and subtask hierarchy well, but does not provide a general-purpose typed link system equivalent to Jira or Yandex Tracker.

### Source notes
- Jira describes a project/space as a configurable container for work items.
- Yandex Tracker documents that every issue belongs to a queue, and also documents a separate native `project` entity that can include queues.
- Asana documents a project as a prioritized list of tasks or a board, and a task as the main work item inside workspaces and projects.
- Jira documents issue links as bidirectional links with configurable link types, each having inward and outward descriptions.
- Yandex Tracker documents links between issues with explicit relationship values such as `relates`, `depends on`, `is dependent by`, `duplicates`, and hierarchy-specific variants.
- Asana documents task dependencies and dependents, which model blocking order rather than a general relation taxonomy.
- Jira and Asana also document hierarchy-style task structures such as work item hierarchy and subtasks.
- Yandex Tracker documents hierarchy-oriented issue links such as parent-task and subtask relations.

### Sources
- Jira: [Projects / spaces overview](https://www.atlassian.com/software/jira/guides/projects/overview)
- Jira: [Issue linking model](https://developer.atlassian.com/cloud/jira/platform/issue-linking-model/)
- Yandex Tracker: [Queue introduction](https://yandex.ru/support/tracker/en/queue-intro)
- Yandex Tracker: [Get project parameters](https://yandex.ru/support/tracker/en/api-ref/projects/get-project)
- Yandex Tracker: [Linking issues](https://yandex.ru/support/tracker/en/api-ref/issues/link-issue)
- Asana: [Projects reference](https://developers.asana.com/reference/projects)
- Asana: [Tasks reference](https://developers.asana.com/reference/tasks)
- Asana: [Set dependencies for a task](https://developers.asana.com/reference/adddependenciesfortask)
- Asana: [Get dependents from a task](https://developers.asana.com/reference/getdependentsfortask)

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
- `ASANA_TOKEN`
- `ASANA_PROJECT_ID` - optional, enables Asana task listing

Local development files:
- `.env.example` - fallback template for local example runs
- `.env` - local override for real local credentials

Examples load variables with this priority:
1. process environment
2. `.env`
3. `.env.example`

## Roadmap
See `ROADMAP.md` for current status, planned work, and future provider candidates.
