# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and the project uses Semantic Versioning.

PyPI releases start at `0.3.0`; earlier `0.1.x` / `0.2.x` tags predate publication and are intentionally omitted here.

Entries below are historical and are not rewritten. The Asana provider
mentioned in `0.3.0` was removed in `0.4.0`.

## [Unreleased]

## [0.4.1] - 2026-11-11

### Added
- Added canonical optional `Task.priority` and `Task.work_type` fields with public `TaskPriority` (`low`, `medium`, `high`) and `TaskWorkType` (`bug`, `feature`, `task`, `refactor`) enums.
- Jira maps `priority.name` and `issuetype.name`; Yandex Tracker maps stable priority/type keys; GitHub maps the native issue type and the `Priority` single-select issue field.
- Provider-specific mapping tables accept only explicitly known values. Unknown values return `None` rather than being guessed.

### Tests and docs
- Added exact mapping and mapper tests for all three providers, including GitHub `Bug + High` and unknown-value cases.
- Documented canonical metadata and provider mappings.

## [0.4.0] - 2026-11-11

### Breaking
- Removed the deprecated Asana provider, its auth config, example, and runtime dependency. Use `trackerkit>=0.3.0,<0.4.0` if Asana support is still required.

### Added
- New `github` provider backed by an asynchronous REST transport: workspaces, repository-backed projects, issue read/create/update, task counting, and relation CRUD.
- GitHub relations use native related issues (`relates`), issue dependencies (`blocks`), and sub-issues (`contains`).
- Stable, versioned GitHub task and relation handles that carry the repository and issue coordinates required by different GitHub APIs.
- GitHub pagination, pull-request filtering, bounded concurrency, and normalized authentication/provider errors with rate-limit details.
- `TrackerClient.close()` and async context-manager support for releasing HTTP resources.

### Changed
- Added direct `httpx` runtime dependency for GitHub REST API access.
- `TaskQuery.limit` is now honored by GitHub task listing; GitHub task list/count operations require `project_id`.

### Documentation and tests
- Replaced Asana examples and environment settings with a read-only GitHub live-validation flow.
- Updated provider, auth, project, task, relation, roadmap, and third-party dependency documentation.
- Added GitHub mapper, query, identifier, transport, client, and relation tests.
- Verified the read-only example against `depensee-dev/trackerkit`: two existing issues and their native `contains` relation were loaded without modifying GitHub data.

## [0.3.2] - 2026-07-18
### Fixed
- Yandex Tracker `list_relations`: fixed inverted direction of `BLOCKS` relations on trackers that return **localized** link labels (e.g. Russian "Зависит от" / "Блокирующая задача"). Such labels never match the configured English relationship values (`is dependent by` / `depends on`), so direction fell back to `direction == "outward"`, which put the *dependent* task as `source_task_id` instead of the *blocker*. The relation is now correctly directed blocker → blocked. Verified against live queue data (`ZIR-27` blocks `ZIR-81`).

### Notes
- Only the **read** path (`list_relations`) is affected. Relation **creation** (`create_relation` / `get_create_relationship`) was already correct and is unchanged; `YandexTrackerRelationMappingConfig` values are unchanged, so no configuration migration is required.
- `RELATES` and `CONTAINS` direction handling is unchanged.

## [0.3.1] - 2026-06-25

Bug-fix release focused on correct queue-scoped task retrieval and cheap task counting.

### Added
- `count_tasks(query)` across the stack: `TrackerClient.count_tasks`, the opt-in `TaskReadCapability.count_tasks` contract, and provider adapters — Jira via `search` with `maxResults=0` (reads `total` without mapping any issue) and Yandex Tracker via the dedicated `/issues/_count` endpoint.

### Fixed
- Yandex Tracker `list_tasks`: queue scoping is now encoded in the query DSL (`Queue: "KEY"`) instead of the SDK's top-level `queue` kwarg, which `/issues/_search` and `/issues/_count` ignore — previously tasks leaked across all queues. A client-side `project_id` filter was added as a safety net.
- Yandex Tracker `list_tasks`: removed manual paging that called `len()` on the SDK's lazy `PaginatedList` (which has no `__len__`); the transport now materializes the paginated iterator inside the worker thread.
- Yandex Tracker user mapping: read the already-loaded "short" representation (`as_dict()`) instead of lazy attribute access, avoiding an N+1 request storm when mapping a whole page of issues.

### Tests
- Updated Yandex query-policy tests for DSL-based queue scoping and combined filters.

## [0.3.0] - 2026-06-17

Stabilization release: faster, stricter, and significantly better tested.

### Breaking
- `AsanaClient.list_tasks` now requires `TaskQuery.project_id` (raises `ProviderCapabilityError` otherwise) — no more silent fan-out over all workspaces × projects.
- Jira `Workspace.id` is now a synthetic `"jira:<host>"` identifier instead of the base URL.
- `JiraMapper._to_user` / `YandexTrackerMapper._to_user` return `None` when no usable identifier exists (previously produced `User(id="None")`).
- `TrackerClient` no longer runs a connection diagnostic before every call; it is cached with a TTL (default 30s). Use `verify_each_call=True` to restore the old behavior.
- `connection_timeout` typed as `float` (was `int`) and validated up-front in the facade.

### Added
- `ConnectionErrorKind` enum (exported from `trackerkit`); `ConnectionDiagnostic.error_kind` is typed by it while preserving `str` comparisons.
- `TaskQuery.limit` — soft pagination cap (honored by Asana).
- `TrackerClient.invalidate_connection_cache()` and constructor parameters `connection_check_ttl`, `verify_each_call`.
- `TaskTrackerClientFactory.register(...) / unregister(...)` — pluggable provider registry.

### Changed / Fixed
- JQL escaping for `project_id` / `assignee_id` / `status_id` in Jira queries.
- Jira `delete_task` and `update_task`: fewer round-trips.
- Jira `update_project`: private SDK usage isolated in a single annotated helper.
- Yandex `list_tasks`: `assignee`, `status`, `updated_since` pushed into the server-side query string.

### Tooling / Tests
- `[tool.ruff]` and `[tool.pytest.ini_options]` configured in `pyproject.toml`; `pytest-asyncio` added to dev deps.
- 73 unit tests covering mappers, query builders, relation policies, relation mapping config, error kinds, the connection guard, and the factory.

### Docs
- New `TECH_ROADMAP.md`.
- Updated `README.md`, `docs/auth.md`, `docs/projects.md`, `docs/tasks.md`.
