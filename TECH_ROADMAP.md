# Technical Roadmap

Engineering-side TODO list for `trackerkit`. Complements `ROADMAP.md` (which
tracks product capabilities, staged release targets, and feature priorities
driven by the host product Depensee) by listing technical debt,
correctness/perf bugs, tooling gaps, and architectural decisions.

Asana was removed in `0.4.0`. GitHub replaced it with a native asynchronous
REST adapter covering issues and all core relation types.

Statuses below were re-verified against the code on 2026-11-11.

## Legend

Priority:
- 🔴 Critical — blocks safe day-to-day work or further stabilization.
- 🟠 Substantial — visible correctness, performance, or encapsulation issue.
- 🟡 Polish — DX improvement, tooling, or future-proofing.

Status:
- `[ ]` Not started.
- `[~]` In progress.
- `[x]` Done.
- `[?]` Decision pending (see "Open Architectural Decisions").

Each item points to the relevant file paths so the work can start without
re-discovering the codebase.

---

## Product alignment (`ROADMAP.md` stages)

Map product milestones to engineering prep. Full checklists live in `ROADMAP.md`.

| Product (ROADMAP) | Suggested engineering first |
| --- | --- |
| **Next** errors + rate limit | New `domain/errors.py` types; shared HTTP/limiter layer or transport wrappers (Jira/Yandex) |
| **Next** `from_config()` | ARCH-1, DEC-1 (`ProviderAuthConfig` entry, `extra="ignore"`) |
| **Next** users + webhooks | New capability modules under `contracts/` + provider packages |
| **Next** relation stability | TEST-2, TEST-5, DEC-2 |
| **Later** custom fields + transitions | Jira/Yandex mappers + transport; expose existing Jira `transition_issue` |
| **Later** comments | `CommentCapability` implementations |
| **Someday** bulk + OAuth | Transport batching; `AuthProvider` without facade provider branches |
| **Someday** capability matrix | POL-6, TEST-5 contract parametrization |

---

## 🔴 Critical

### SEC-1. Rotate live tokens and stop storing real secrets in `.env`
- [ ] Rotate `JIRA_TOKEN` for `https://jira.evt-s.ru/`. (manual user action)
- [ ] Rotate `YANDEX_TOKEN` and confirm whether `YANDEX_CLOUD_ORG_ID` is
      sensitive in this org context. (manual user action)
- [ ] Move local credentials out of `trackerkit/.env`. Options:
      system keychain, 1Password CLI, `direnv` with encrypted backend,
      or a one-time short-lived dev token with minimum scope. (manual user action)
- [ ] Replace the current `.env` content with placeholders (mirror
      `.env.example`) so the file is safe to keep in the workspace. (manual user action)

Files:
- `trackerkit/.env`
- `trackerkit/.env.example`
- `trackerkit/.gitignore` (already correct — `.env` is ignored)

Note: `git log -S` confirms tokens were never committed. The risk is local
plaintext exposure, including LLM workspace context.

### TEST-1. Bootstrap test infrastructure
- [x] Add `pytest-asyncio` to dev-dependencies.
- [x] Add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and
      `testpaths = ["tests"]`.
- [x] Create `tests/conftest.py` with shared fixtures (fake transports,
      sample issue/queue payloads).

Files:
- `pyproject.toml`
- `tests/conftest.py` (new)

### TEST-2. Unit tests for relation policies
- [~] `JiraRelationPolicy._matches_mapping` — outward/inward label match,
      missing labels. (case sensitivity has no explicit test)
- [~] `JiraRelationPolicy._to_relation_from_issue_context` — direction
      derived from inward vs outward, missing IDs. (basic case covered via list_relations)
- [x] `JiraRelationPolicy.parse_structural_relation_id` /
      `build_structural_relation_id` — round-trip and malformed input.
- [x] `JiraRelationPolicy.list_relations` — deduplication when both
      hierarchy and issue links describe the same relation.
- [~] `YandexTrackerRelationPolicy._find_relation_type` —
      `_TYPE_ID_ALIASES` coverage, label fallback. (covered indirectly)
- [~] `YandexTrackerRelationPolicy._is_outward_direction` —
      `RELATES` symmetry vs directional types. (covered indirectly)
- [x] `YandexTrackerRelationPolicy.split_relation_id` — empty parts,
      missing separator.

Files:
- `src/trackerkit/providers/jira/relations.py`
- `src/trackerkit/providers/yandex_tracker/relations.py`

### TEST-3. Unit tests for relation mapping config
- [x] `JiraRelationMappingConfig.from_env` — empty values, `;` and `|`
      parsing, malformed entries (raise `ConfigurationError`).
- [ ] `JiraRelationMappingConfig._merge_link_mappings` — overrides do
      not duplicate, defaults survive when env is silent. (no direct test;
      exercised only through `from_env`)
- [x] `JiraContainsMode` switch behavior with and without
      `JIRA_CONTAINS_MODE` env override.
- [x] `RelationMappingConfig.from_env` end-to-end smoke test with a
      synthetic mapping.

Files:
- `src/trackerkit/domain/relation_mapping.py`

### TEST-4. Unit tests for mappers
- [x] `JiraMapper._parse_datetime` — `Z` suffix, naive datetime, date-only.
- [~] `JiraMapper._to_user` — every fallback path, including the
      "all attributes None" case (now returns `None`, see CORR-3).
      `_to_status` has no tests.
- [~] `YandexTrackerMapper._parse_datetime` and `_to_user`. (`_to_user` covered)
- [x] `GitHubMapper` — issue fields, statuses, users, workspaces, repositories,
      datetime parsing, and stable task handles.

Files:
- `src/trackerkit/providers/jira/mappers.py`
- `src/trackerkit/providers/yandex_tracker/mappers.py`
- `src/trackerkit/providers/github/mappers.py`

### TEST-5. Contract tests for `TaskTrackerClient`
- [ ] One shared parametrized test module that runs against
      `JiraClient`, `YandexTrackerClient`, `GitHubClient` with mocked
      transports.
- [ ] Verify each `Capability` ABC method either succeeds or raises
      `ProviderCapabilityError` per the documented capability matrix.
- [x] `TrackerClient._build_connection_error` — `error_kind` →
      domain error type mapping.
- [x] GitHub adapter tests cover task and relation operations with a mocked transport.

Files:
- `tests/contract/test_task_tracker_client.py` (new)
- `tests/providers/github/`
- `src/trackerkit/tracker_client.py`

### PERF-1. Stop running connection guard before every call — DONE
The facade used to make a `myself`-style provider request on every business
method, which contradicted the lazy semantics declared in `docs/auth.md` and
multiplied provider rate-limit cost (especially for paginated calls like
`YandexTrackerClient.list_tasks`).

- [x] Decide on the strategy: cached TTL diagnostic (default 30s) +
      opt-in `verify_each_call`, with `invalidate_connection_cache()`
      escape hatch.
- [x] Implement, document the new behavior in `docs/auth.md`.
- [x] Cover with a test that asserts only one diagnostic call per
      successful business call sequence.

Files:
- `src/trackerkit/tracker_client.py`
- `docs/auth.md`

---

## 🟠 Substantial

### ARCH-1. Remove provider-specific knowledge from the facade — DONE
The facade used to special-case Jira with an
`if self._provider is Provider.JIRA:` branch around `max_retries`, which
blocked adding new providers (Bitrix24, Trello) without editing the central
facade. See "Open Architectural Decisions / DEC-1" for the direction beyond
this minimum step.

- [x] Add `extra="ignore"` to the auth configs — set on the base
      `ProviderAuthConfig` (`contracts/auth.py`), inherited by Yandex and GitHub.
- [x] Pass `max_retries` unconditionally; let unrelated providers
      ignore it (`tracker_client.py`).
- [x] Drop the `if self._provider is Provider.JIRA:` branch.

Files:
- `src/trackerkit/contracts/auth.py`
- `src/trackerkit/tracker_client.py`

### ARCH-2. Stop using private SDK API in Jira `update_project`

```183:188:src/trackerkit/providers/jira/transport.py
    async def _raw_put_project(...)
```

`_get_url` and `_session` are internal to `pycontribs/jira` and may
break on a minor SDK update.

- [ ] Replace with a dedicated thin HTTP layer (e.g. `httpx`) for the
      few endpoints the SDK does not cover, or
- [~] Encapsulate the workaround in a single helper with an explicit
      `# uses private SDK API; revisit on jira>=X` comment and a test
      that fails on regression. (helper `_raw_put_project` with the comment
      exists; the regression test does not)

Files:
- `src/trackerkit/providers/jira/transport.py`

### ARCH-3. Remove encapsulation leak in the Jira example

```141:141:examples/jira_example.py
        jira_transport = client._client._transport
```

Double-private access through the facade is a smell. Symmetric
mutable state in transport:

```c:\Users\root\Work\depensee\trackerkit\src\trackerkit\providers\jira\transport.py
    self._last_issue_link_debug: dict[str, Any] | None = None
```

is racy under concurrent calls.

- [ ] Replace `_last_issue_link_debug` with `logging` calls under a
      named library logger (`trackerkit.providers.jira`).
- [ ] Drop `JiraTransport.get_last_issue_link_debug`.
- [ ] Remove `client._client._transport` from `examples/jira_example.py`;
      log via the standard `logging` config instead.

Files:
- `src/trackerkit/providers/jira/transport.py`
- `examples/jira_example.py`

### ARCH-4. GitHub native async transport and lifecycle — DONE

- [x] Use `httpx.AsyncClient` directly instead of wrapping a synchronous SDK
      that may lag behind sub-issue, dependency, and related-issue endpoints.
- [x] Add `TrackerClient.close()` and async context-manager support so HTTP
      connections are released explicitly.

Files:
- `src/trackerkit/providers/github/transport.py`
- `src/trackerkit/tracker_client.py`

### PERF-2. Yandex `list_tasks`: push filters to the server — DONE
`build_issue_search_params` used to return `query=None` and ignore
`assignee_id` / `status_id` / `updated_since`, forcing client-side filtering
after a full paginated scan.

- [x] Build a Yandex `query` string for `assignee`, `status`, and
      `updated >= <date>` when the corresponding fields are set
      (`yandex_tracker/queries.py`; queue scoping added in `0.3.1`).
- [x] Keep client-side filtering as a fallback (`filter_tasks`).
- [x] Cover with a test that asserts the server query string
      (`tests/providers/yandex_tracker/test_queries.py`).

Files:
- `src/trackerkit/providers/yandex_tracker/queries.py`
- `src/trackerkit/providers/yandex_tracker/client.py`

### PERF-3. GitHub `list_tasks`: require repository scope — DONE
Without `project_id`, an adapter would need to walk every visible repository or
use a bounded global search. Both are unsafe defaults for large accounts.

- [x] Require `project_id` for list/count/create and raise
      `ProviderCapabilityError` otherwise.
- [x] Use repository issue pagination for listing and issue search only for count.
- [x] Document the constraint in `docs/tasks.md`.

Files:
- `src/trackerkit/providers/github/client.py`
- `docs/tasks.md`

### PERF-4. Reduce round trips in Jira CRUD — DONE
- [x] `JiraClient.delete_task` deletes by id/key directly
      (`delete_issue_by_id`), without the preceding `get_issue(...)`.
- [x] `JiraClient.update_task` reuses the issue it already read instead of
      reading twice.

Files:
- `src/trackerkit/providers/jira/client.py`
- `src/trackerkit/providers/jira/transport.py`

### CORR-1. JQL escaping in `JiraQueryBuilder` — DONE
A `"` or `\` inside a query field used to break JQL.

- [x] Escape `"` and `\` in user-provided query fields
      (`_escape_jql_string` in `jira/queries.py`, applied to
      `project_id` / `assignee_id` / `status_id`).
- [x] Cover with a test (`tests/providers/jira/test_queries.py`).

Files:
- `src/trackerkit/providers/jira/queries.py`

### CORR-2. Workspace.id for Jira is the base URL — DONE
`JiraMapper.to_workspace()` used to set `Workspace.id` to the base URL,
which was tempting to misuse as a Jira API endpoint.

- [x] Use a synthetic non-URL form `jira:<host>` (`jira/mappers.py`;
      breaking change in `0.3.0`, covered by `test_mappers.py`).
- [x] Document `Workspace.id` for Jira as synthetic (`docs/projects.md`).

Files:
- `src/trackerkit/providers/jira/mappers.py`
- `docs/projects.md`

### CORR-3. User mapper produces `User(id="None")` on missing fields — DONE
Both `_to_user` implementations used to `str(...)` a `None`, yielding the
literal string `"None"`.

- [x] Return `User | None` honestly when no usable id can be derived
      (`jira/mappers.py`, `yandex_tracker/mappers.py`; breaking in `0.3.0`).
- [x] Cover with a test exercising an empty user payload (`test_mappers.py`
      in both providers).

Files:
- `src/trackerkit/providers/jira/mappers.py`
- `src/trackerkit/providers/yandex_tracker/mappers.py`

### CORR-4. GitHub pagination and result limits — DONE
GitHub list endpoints are page-based and Issues endpoints may include pull
requests.

- [x] Follow `Link: rel="next"` with `per_page=100`.
- [x] Apply `TaskQuery.limit` after pull-request filtering.
- [x] Bound transport concurrency and expose explicit HTTP cleanup.
- [x] Cover pagination, filtering, and limits in `tests/providers/github/`.

Files:
- `src/trackerkit/providers/github/transport.py`
- `src/trackerkit/domain/models.py`
- `docs/tasks.md`

---

## 🟡 Polish / DX

### POL-1. Introduce `ConnectionErrorKind` enum — DONE
`ConnectionDiagnostic.error_kind` used to be `str | None` against literals
`"authentication"` / `"configuration"` / `"capability"` / `"provider"`.

- [x] Define `ConnectionErrorKind(str, Enum)` in `domain/enums.py`.
- [x] Replace literals in `domain/errors.py::get_error_kind` and the facade.
- [x] Re-export from `__init__.py` (public surface since `0.3.0`; covered by
      `tests/domain/test_error_kinds.py`).

Files:
- `src/trackerkit/domain/enums.py`
- `src/trackerkit/domain/errors.py`
- `src/trackerkit/tracker_client.py`

### POL-2. Type/value consistency for `connection_timeout` — DONE
- [x] `connection_timeout` is typed `float = 3.0`, matching
      `ProviderAuthConfig.timeout_seconds` and the docs.
- [x] Early validation in the facade raises a domain error instead of a raw
      `pydantic.ValidationError` (covered by `tests/test_tracker_client.py`).

Files:
- `src/trackerkit/tracker_client.py`
- `docs/auth.md`

### POL-3. Deduplicate `TrackerKitError` — DONE
`TrackerKitError = TrackerClientError` used to be defined twice (in
`domain/errors.py` and in `__init__.py`). One source of truth now.

- [x] Define the alias in `domain/errors.py` only; re-export from
      `domain/__init__.py` and `__init__.py`.

Files:
- `src/trackerkit/domain/errors.py`
- `src/trackerkit/__init__.py`

### POL-4. Pluggable provider registry
`TaskTrackerClientFactory` hardcodes the three providers.

- [x] Add `register(provider, config_cls, client_cls)` / `unregister(...)` so
      external code can plug in adapters without editing the library.
- [~] Cover with a test that registers a fake provider and round-trips
      through `TrackerClient`. (the factory itself is tested in
      `tests/factory/test_client_factory.py`; the round-trip through the
      facade is not)

Files:
- `src/trackerkit/factory/client_factory.py`
- `src/trackerkit/domain/enums.py` (Provider may need to accept dynamic values)

### POL-5. Decide Python lower bound — DONE
Code uses `from datetime import UTC` (3.11+) and modern generics.

- [x] Keep 3.12 as the lower bound (`requires-python = ">=3.12,<3.15"`) and
      document the reasoning in `README.md`.

Files:
- `pyproject.toml`
- `README.md`

### POL-6. Capability matrix in code, not just docs
`users` and `comments` are part of the unified `TaskTrackerClient`
composite, but every adapter raises `ProviderCapabilityError`. This
gives IDE autocomplete a misleading signal.

- [ ] Decide whether to keep the always-raising stubs (current behavior)
      or split into optional ports per provider.
- [ ] If splitting, expose a runtime `client.supports(capability)` check
      and update `docs/auth.md`.

Files:
- `src/trackerkit/contracts/task_tracker_client.py`
- `src/trackerkit/providers/base.py`
- providers as needed

### POL-7. Clean up local `dist/` artifacts
`dist/` holds stale build output. The pre-rename
`depensee_tracker_client-*` files are gone; what lingers now are
`trackerkit-0.3.{0,1,2}` wheels and sdists.

- [ ] Delete the old artifacts. `dist/` is already in `.gitignore`,
      so this is a one-time local cleanup.

Files:
- `dist/`

---

## Tooling

### TOOL-1. Ruff configuration — DONE

- [x] `[tool.ruff]` with `target-version = "py312"` and `[tool.ruff.lint]`
      selecting `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF` (`pyproject.toml`).
- [x] Run `ruff check --fix` once and review the diff.

Files:
- `pyproject.toml`

### TOOL-2. Pytest configuration — DONE
- [x] `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`,
      `testpaths = ["tests"]` and `addopts = "-q"` (`pyproject.toml`).

Files:
- `pyproject.toml`

### TOOL-3. Pre-commit hooks
- [ ] Add `.pre-commit-config.yaml` with at minimum: `ruff`, `ruff-format`,
      and `check-toml`.
- [ ] Document `pre-commit install` in `README.md`.

Files:
- `.pre-commit-config.yaml` (new)
- `README.md`

### TOOL-4. CI pipeline (GitHub Actions)
No `.github/workflows/` directory exists yet.

- [ ] Add `ci.yml` running on push/PR: `poetry install`, `ruff check`,
      `pyright`, `pytest`.
- [ ] Matrix over Python 3.12 (and 3.13 if it stays in classifiers).

Files:
- `.github/workflows/ci.yml` (new)

---

## Open Architectural Decisions

These items are blocked on a deliberate choice. They are intentionally
not actionable yet — opening any of them without a decision risks
churn.

### DEC-1. Facade signature evolution
`TrackerClient(provider, auth_data, connection_timeout, max_retries,
relation_mapping)` mixes provider-agnostic concerns and Jira-only
parameters. Three options live in chat history:

- A. Minimal fix — `extra="ignore"` in Yandex/GitHub auth configs. **Already shipped** via ARCH-1.
- B. Additive — add `TrackerClient.from_config(config: ProviderAuthConfig)` next to the existing constructor.
- C. Breaking — single constructor `TrackerClient(auth_config: ProviderAuthConfig, relation_mapping=None)`, shipped as a breaking release.

- [?] Pick A, B, or C before further facade signature changes.

### DEC-2. Shape of `Relation.id`
`Relation.id: str | None` remains an opaque dispatch token whose
format is parsed by Jira (`jira-contains:<src>:<dst>` or raw link id),
Yandex (`<issue_id>:<link_id>`), and GitHub (versioned, encoded task handles).

Options from chat history:
- A. Keep `str`, document as opaque, add explicit format versioning.
- B. Introduce `RelationHandle` model with `serialize()`/`deserialize()`
     and accept `RelationHandle | str` in delete/update.
- C. Drop dispatch tokens entirely — `delete_relation` accepts a
     `DeleteRelationInput(source_task_id, target_task_id, relation_type)`,
     symmetric with `Create/UpdateRelationInput`.

- [x] GitHub implements option A with `github:relation:v1:` IDs.
- [?] Choose one cross-provider contract before changing existing Jira/Yandex IDs.

---

## Suggested Execution Order

### Phase A — close current maintenance

1. SEC-1 (manual token hygiene).
2. TEST-2, TEST-3, TEST-4; finish TEST-5 contract skeleton.
3. ARCH-2 regression test, ARCH-3 (logging instead of debug state).
4. TOOL-3, TOOL-4 (CI + pre-commit); POL-7 local cleanup.
5. Resolve DEC-1 (`from_config` is the remaining part) and the cross-provider
   part of DEC-2.

Closed in `0.3.0`–`0.4.0`: TEST-1, PERF-1..4, ARCH-1, ARCH-4, CORR-1..4,
POL-1..3, POL-5, TOOL-1, TOOL-2. GitHub relation IDs use a versioned opaque format.

### Phase B — the Next stage (see `ROADMAP.md`)

1. Structured errors + `RateLimitError`.
2. Shared rate limiter on provider transports.
3. `TrackerClient.from_config()`.
4. `UserCapability` + `WebhookCapability` (Jira, Yandex Tracker).
5. Relation tests locked under DEC-2.

### Phase C — Later / Someday

1. Custom fields + Jira transitions API (Later).
2. Comments (Later).
3. Bulk, OAuth, token hook, POL-6 capability matrix (Someday).
