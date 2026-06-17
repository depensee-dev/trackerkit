# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and the project uses Semantic Versioning.

## [Unreleased]

## [0.3.0] - 2026-04-26

Stabilization release on top of `0.1.1`: faster, stricter, and significantly better tested.

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

## [0.1.1] - 2026-04-26
### Changed
- Renamed distribution package from `depensee-tracker-client` to `trackerkit`.
- Renamed Python import namespace from `depensee_tracker_client` to `trackerkit`.
- Updated README, docs, examples, and package metadata for the new name.

### Added
- MIT license.
- `ROADMAP.md`.
- `THIRD_PARTY_LICENSES.md` (third-party runtime dependency license summary).
- Clarified relation mapping configuration and provider capability documentation.

## [0.1.0] - 2026-04-15
### Added
- initial public project structure for the unified async tracker client;
- provider adapters for Jira, Yandex Tracker, and Asana;
- shared contracts and domain models for tasks, projects, workspaces, users, comments, and relations;
- example scripts and documentation for auth, projects, and tasks.

### Changed
- package name finalized as `trackerkit`.
