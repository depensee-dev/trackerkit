# Auth

## Signature
```python
TrackerClient(
    provider: str,
    auth_data: dict,
    connection_timeout: float = 3.0,
    max_retries: int = 0,
    relation_mapping: RelationMappingConfig | None = None,
    connection_check_ttl: float = 30.0,
    verify_each_call: bool = False,
)
await client.check_connection() -> bool
await client.ensure_connection() -> None
await client.get_connection_diagnostic() -> ConnectionDiagnostic
client.invalidate_connection_cache() -> None
await client.close() -> None
```

`TrackerClient` is also an async context manager. Use `async with` or call
`close()` explicitly so the GitHub HTTP transport releases its connections.

## Providers
- `jira`
- `yandex_tracker`
- `github`

## Jira

### `auth_data`
- `base_url`: `str`
- `email`: `str | None`
- `api_token`: `str | None`
- `access_token`: `str | None`

### Validation
- required: `base_url`
- required: one of `api_token` or `access_token`
- `JiraClient` uses token auth only
- pass Jira token in `access_token` or `api_token`

### Example
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

## Yandex Tracker

### `auth_data`
- `token`: `str | None`
- `iam_token`: `str | None`
- `org_id`: `str | None`
- `cloud_org_id`: `str | None`

### Validation
- required: one of `token` or `iam_token`
- required: one of `org_id` or `cloud_org_id`

### Example
```python
from trackerkit import TrackerClient

client = TrackerClient(
    provider="yandex_tracker",
    auth_data={
        "token": "oauth-token",
        "org_id": "your-org-id",
    },
    connection_timeout=3,
)
```

## GitHub

### `auth_data`
- `access_token`: `str`, required
- `base_url`: `str`, default `https://api.github.com`
- `api_version`: `str`, default `2026-03-10`
- `max_concurrency`: `int`, default `10`, allowed range `1..100`

The current connection and repository discovery flow uses `/user`, `/user/orgs`,
and `/user/repos`. Use a personal access token or a GitHub/OAuth App **user**
access token. GitHub App installation access tokens are not supported by this
flow yet.

For read-only access to issues, grant repository `Issues: read` and `Metadata:
read`. Issue and relation writes require `Issues: write`. Repository discovery
only returns repositories visible to the configured token. Organization SSO or
repository selection policies can further restrict the result.

The adapter pins `X-GitHub-Api-Version` and targets the current GitHub.com APIs,
including related issues, dependencies, and sub-issues. Compatibility with a
particular GitHub Enterprise Server version must be verified separately when
using a custom `base_url`.

### Example
```python
from trackerkit import GitHubAuthConfig, TrackerClient

config = GitHubAuthConfig(
    access_token="secret",
    max_concurrency=10,
)

async with TrackerClient(
    provider="github",
    auth_data=config.model_dump(),
    connection_timeout=3,
) as client:
    await client.ensure_connection()
```

## Errors
- `ConfigurationError` if required auth fields are missing
- `AuthenticationError` if the client is disconnected or provider auth is invalid
- `ConfigurationError` or enum coercion `ValueError` if `provider` is not supported
- GitHub HTTP errors are normalized to `AuthenticationError` or `ProviderError`;
  rate-limit responses retain `Retry-After` / reset details in the message

## Connection Options
- `connection_timeout` controls provider request timeout in seconds
- `max_retries` controls additional retry attempts for Jira transport; GitHub currently reports rate limits instead of automatically waiting
- `relation_mapping` overrides default relation normalization and provider link mapping for Jira/Yandex
- `connection_check_ttl` (seconds) caches a successful auth check; `0` disables caching
- `verify_each_call` forces a fresh provider auth check before every business call
- these connection-guard options are passed separately from `auth_data`
- defaults are defined on `TrackerClient`, not in environment variables
- current defaults: `connection_timeout=3.0`, `max_retries=0`, `connection_check_ttl=30.0`, `verify_each_call=False`
- `connection_timeout <= 0`, `max_retries < 0`, and `connection_check_ttl < 0` raise `ConfigurationError`

## Capability Scope
- `workspaces`, `projects`, and `tasks` are implemented by Jira, Yandex Tracker, and GitHub
- relation CRUD is implemented by all three providers
- GitHub issue create/update is implemented; direct issue deletion is unsupported
- GitHub repository create/update/delete is unsupported in the current adapter
- users and comments are present in the shared contract as future capabilities; provider adapters currently raise `ProviderCapabilityError`

## Relation Mapping
- `RelationMappingConfig` is an optional runtime config for Jira/Yandex relation semantics
- the primary path is explicit config construction and passing it into `TrackerClient`
- `RelationMappingConfig.from_env()` is an opt-in helper for examples, tests, or host services that intentionally use environment-based settings
- by default:
  - Jira maps `relates` and `blocks` through issue links
  - Jira maps `contains` through structural hierarchy
  - Yandex Tracker maps `relates`, `blocks`, and `contains` through native link values
  - GitHub maps them to related issues, dependencies, and sub-issues without configurable labels
- pass a custom config only when provider defaults do not match your workspace setup

### Example
```python
from trackerkit import (
    JiraContainsMode,
    JiraLinkTypeMapping,
    JiraRelationMappingConfig,
    RelationMappingConfig,
    RelationType,
    TrackerClient,
)

relation_mapping = RelationMappingConfig(
    jira=JiraRelationMappingConfig(
        contains_mode=JiraContainsMode.HYBRID,
        contains_link_mappings=(
            JiraLinkTypeMapping(
                relation_type=RelationType.CONTAINS,
                type_name="Contains",
                outward_label="contains",
                inward_label="is contained by",
            ),
        ),
    )
)

client = TrackerClient(
    provider="jira",
    auth_data={
        "base_url": "https://your-domain.atlassian.net",
        "access_token": "secret",
    },
    relation_mapping=relation_mapping,
)
```

## Diagnostics
- `TrackerClient(...)` validates configuration immediately and raises `ConfigurationError` for invalid common options
- provider network calls are lazy and usually start on `check_connection()` or the first business method call
- `check_connection()` returns only `bool`
- `ensure_connection()` writes a named library log entry on failure and raises a normalized domain error
- `get_connection_diagnostic()` returns structured connection details with `provider`, `is_connected`, `error_kind`, `error_type`, and `message`

## Connection Guard
- facade methods call `ensure_connection()` before provider operations
- a successful auth check is cached for `connection_check_ttl` seconds, so subsequent
  calls within the window do not pay an extra provider round-trip
- pass `verify_each_call=True` if your host service needs strict per-call verification
- after out-of-band auth changes (e.g. token rotation) call `invalidate_connection_cache()`
  to force the next call to re-verify
- if connection is invalid, the facade raises a normalized domain error based on the real diagnostic cause

## Internal Notes
- provider adapters are split into `transport`, `queries`, `mappers`, and `errors`
- the public `TrackerClient` facade stays thin and delegates to provider capabilities
- auth configs and shared DTOs remain `Pydantic` models
- the public API of the library is async
- provider transports may use native async clients or wrap sync SDKs internally
- GitHub uses a native `httpx.AsyncClient` and an adapter-local concurrency limiter
- the library does not load `.env` files; configuration is injected from the host service
- env-based helpers read process environment only when called explicitly
- local `examples/` may load `.env.example` and `.env` only for manual development runs
- auth credentials in examples are loaded with precedence: process environment -> `.env` -> `.env.example`

## Host Service Example
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

from trackerkit import TrackerClient


class TrackerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    github_token: str


settings = TrackerSettings()

client = TrackerClient(
    provider="github",
    auth_data={"access_token": settings.github_token},
)
```
