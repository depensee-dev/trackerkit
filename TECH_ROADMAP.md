# Technical Roadmap

Engineering-side TODO list for `trackerkit`. Complements `ROADMAP.md` (which
tracks product capabilities, release targets 0.3–0.5, and ChainForge-driven
feature priorities) by listing technical debt, correctness/perf bugs, tooling
gaps, and architectural decisions.

## Legend

Priority:
- 🔴 Critical — blocks safe day-to-day work or stabilization to 0.3.0.
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

## Product alignment (`ROADMAP.md` 0.3–0.5)

Map product milestones to engineering prep. Full checklists live in `ROADMAP.md`.

| Product (ROADMAP) | Suggested engineering first |
| --- | --- |
| **0.3.0** errors + rate limit | New `domain/errors.py` types; shared HTTP/limiter layer or transport wrappers (Jira/Yandex) |
| **0.3.0** `from_config()` | ARCH-1, DEC-1 (`ProviderAuthConfig` entry, `extra="ignore"`) |
| **0.3.0** users + webhooks | New capability modules under `contracts/` + provider packages |
| **0.3.0** relation stability | TEST-2, TEST-5, DEC-2 |
| **0.4.0** custom fields + transitions | Jira/Yandex mappers + transport; expose existing Jira `transition_issue` |
| **0.4.0** comments | `CommentCapability` implementations |
| **0.5.0** bulk + OAuth | Transport batching; `AuthProvider` without facade provider branches |
| **0.5.0** capability matrix | POL-6, TEST-5 contract parametrization |

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
- [x] `JiraRelationPolicy._matches_mapping` — outward/inward label match,
      case sensitivity, missing labels.
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
- [x] `JiraRelationMappingConfig._merge_link_mappings` — overrides do
      not duplicate, defaults survive when env is silent.
- [x] `JiraContainsMode` switch behavior with and without
      `JIRA_CONTAINS_MODE` env override.
- [x] `RelationMappingConfig.from_env` end-to-end smoke test with a
      synthetic mapping.

Files:
- `src/trackerkit/domain/relation_mapping.py`

### TEST-4. Unit tests for mappers
- [x] `JiraMapper._parse_datetime` — `Z` suffix, naive datetime, date-only.
- [x] `JiraMapper._to_user` / `_to_status` — every fallback path,
      including the "all attributes None" case (now returns `None`, see CORR-3).
- [~] `YandexTrackerMapper._parse_datetime` and `_to_user`. (`_to_user` covered)
- [ ] `AsanaMapper._parse_datetime` (`due_at` vs `due_on`) and
      `_to_status` completion mapping.

Files:
- `src/trackerkit/providers/jira/mappers.py`
- `src/trackerkit/providers/yandex_tracker/mappers.py`
- `src/trackerkit/providers/asana/mappers.py`

### TEST-5. Contract tests for `TaskTrackerClient`
- [ ] One shared parametrized test module that runs against
      `JiraClient`, `YandexTrackerClient`, `AsanaClient` with mocked
      transports.
- [ ] Verify each `Capability` ABC method either succeeds or raises
      `ProviderCapabilityError` per the documented capability matrix.
- [x] `TrackerClient._build_connection_error` — `error_kind` →
      domain error type mapping.

Files:
- `tests/contract/test_task_tracker_client.py` (new)
- `src/trackerkit/tracker_client.py`

### PERF-1. Stop running connection guard before every call
The facade currently makes a `myself`-style provider request on every
business method:

```105:108:src/trackerkit/tracker_client.py
    async def _execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        await self._ensure_connection()
        return await operation()
```

This contradicts the lazy semantics declared in `docs/auth.md` and
multiplies provider rate-limit cost (especially for paginated calls
like `YandexTrackerClient.list_tasks`).

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
The facade currently special-cases Jira:

```60:62:src/trackerkit/tracker_client.py
        if self._provider is Provider.JIRA:
            config_data["max_retries"] = max_retries
```

This blocks adding new providers (Bitrix24, Trello) without editing
the central facade. See "Open Architectural Decisions / DEC-1" for the
preferred direction. Minimum non-breaking step:

- [ ] Add `model_config = ConfigDict(frozen=True, extra="ignore")` to
      `YandexTrackerAuthConfig` and `AsanaAuthConfig`.
- [ ] Pass `max_retries` unconditionally; let unrelated providers
      ignore it.
- [ ] Drop the `if self._provider is Provider.JIRA:` branch.

Files:
- `src/trackerkit/contracts/auth.py`
- `src/trackerkit/tracker_client.py`

### ARCH-2. Stop using private SDK API in Jira `update_project`

```155:157:src/trackerkit/providers/jira/transport.py
        url = client._get_url(f"project/{project_id}")
        await self._run(client._session.put, url, data=json.dumps(data))
```

`_get_url` and `_session` are internal to `pycontribs/jira` and may
break on a minor SDK update.

- [ ] Replace with a dedicated thin HTTP layer (e.g. `httpx`) for the
      few endpoints the SDK does not cover, or
- [ ] Encapsulate the workaround in a single helper with an explicit
      `# uses private SDK API; revisit on jira>=X` comment and a test
      that fails on regression.

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

### ARCH-4. Asana: stop silently discarding `relation_mapping`

```30:31:src/trackerkit/providers/asana/client.py
    ) -> None:
        del relation_mapping
```

- [ ] Just remove the `del relation_mapping` line; the parameter is
      already accepted at the signature level and `BaseTaskTrackerAdapter`
      raises `ProviderCapabilityError` on `create_relation`.
- [ ] If/when Asana relations are implemented, wire `relation_mapping`
      through properly.

Files:
- `src/trackerkit/providers/asana/client.py`

### PERF-2. Yandex `list_tasks`: push filters to the server
`YandexTrackerQueryPolicy.build_issue_search_params` returns
`query=None` and ignores `assignee_id` / `status_id` / `updated_since`,
forcing client-side filtering after a full paginated scan.

- [ ] Build a Yandex `query` string for `assignee`, `status`, and
      `updated >= <date>` when the corresponding fields are set.
- [ ] Keep client-side filtering as a fallback for fields that cannot
      be expressed server-side.
- [ ] Cover with a test that asserts the server query string.

Files:
- `src/trackerkit/providers/yandex_tracker/queries.py`
- `src/trackerkit/providers/yandex_tracker/client.py`

### PERF-3. Asana `list_tasks`: stop walking every workspace and project
Without `project_id` the adapter iterates every workspace × every
project. For a real Asana org this is a stampede.

- [ ] Require `project_id` (or `workspace_id`) and raise
      `ProviderCapabilityError` otherwise, matching `create_task`.
- [ ] Update `docs/tasks.md` with the constraint.

Files:
- `src/trackerkit/providers/asana/client.py`
- `docs/tasks.md`

### PERF-4. Reduce round trips in Jira CRUD
- [ ] `JiraClient.delete_task` does a full `get_issue(...)` only to
      delete; switch to deleting by id/key directly via SDK.
- [ ] `JiraClient.update_task` reads the issue twice (once before
      update, once after); reuse the second read or skip it when no
      caller needs the refreshed entity.

Files:
- `src/trackerkit/providers/jira/client.py`
- `src/trackerkit/providers/jira/transport.py`

### CORR-1. JQL escaping in `JiraQueryBuilder`

```19:23:src/trackerkit/providers/jira/queries.py
        if query.project_id:
            clauses.append(f'project = "{query.project_id}"')
```

A `"` or `\` inside a query field breaks JQL.

- [ ] Either escape `"` and `\` in user-provided query fields, or
      validate input against a strict regex (`^[A-Za-z0-9_-]+$` for
      project/status keys).
- [ ] Cover with a test.

Files:
- `src/trackerkit/providers/jira/queries.py`

### CORR-2. Workspace.id for Jira is the base URL
`JiraMapper.to_workspace()` sets `Workspace.id` to `self._base_url`,
which is tempting to misuse as a Jira API endpoint.

- [ ] Use a synthetic but non-URL form, e.g. `f"jira:{parsed.netloc}"`.
- [ ] Document `Workspace.id` for Jira as "synthetic, not a Jira API id".

Files:
- `src/trackerkit/providers/jira/mappers.py`
- `docs/projects.md`

### CORR-3. User mapper produces `User(id="None")` on missing fields
`JiraMapper._to_user` (and `YandexTrackerMapper._to_user`) chain
fallbacks that all eventually `str(...)` a `None`, yielding the literal
string `"None"`.

- [ ] Return `User | None` honestly when no usable id can be derived.
- [ ] Cover with a test that exercises an "empty user" payload from the
      provider.

Files:
- `src/trackerkit/providers/jira/mappers.py`
- `src/trackerkit/providers/yandex_tracker/mappers.py`

### CORR-4. Asana `_materialize` flattens paginators eagerly

```c:\Users\root\Work\depensee\trackerkit\src\trackerkit\providers\asana\client.py
    def _materialize(self, value: Any) -> list[dict[str, Any]]:
        ...
        return list(value)
```

The Asana SDK returns a paginator. `list(value)` pulls every page
into memory.

- [ ] Either iterate explicitly with a configurable `limit`, or expose
      pagination on `TaskQuery` (`limit`, `cursor`).
- [ ] Document the limit in `docs/tasks.md`.

Files:
- `src/trackerkit/providers/asana/client.py`
- `src/trackerkit/domain/models.py`
- `docs/tasks.md`

---

## 🟡 Polish / DX

### POL-1. Introduce `ConnectionErrorKind` enum
`ConnectionDiagnostic.error_kind` is `str | None`, but the codebase
uses literals `"authentication"` / `"configuration"` / `"capability"` /
`"provider"`.

- [ ] Define `ConnectionErrorKind(str, Enum)` in `domain/enums.py`.
- [ ] Replace literals in `domain/errors.py::get_error_kind` and the
      facade.
- [ ] Re-export from `__init__.py` if it becomes public surface.

Files:
- `src/trackerkit/domain/enums.py`
- `src/trackerkit/domain/errors.py`
- `src/trackerkit/tracker_client.py`

### POL-2. Type/value consistency for `connection_timeout`
- [ ] Switch `TrackerClient.__init__(connection_timeout: int = 3)` to
      `float = 3.0` to match `ProviderAuthConfig.timeout_seconds: float`
      and the docs.
- [ ] Add an early `if connection_timeout <= 0: raise ConfigurationError`
      check in the facade so users get a domain error instead of a raw
      `pydantic.ValidationError`.

Files:
- `src/trackerkit/tracker_client.py`
- `docs/auth.md`

### POL-3. Deduplicate `TrackerKitError`
`TrackerKitError = TrackerClientError` is defined twice (in
`domain/errors.py` and in `__init__.py`). Keep one source of truth.

- [ ] Define the alias in `domain/errors.py` only; re-export from
      `__init__.py`.

Files:
- `src/trackerkit/domain/errors.py`
- `src/trackerkit/__init__.py`

### POL-4. Pluggable provider registry
`TaskTrackerClientFactory` hardcodes the three providers.

- [ ] Add `register(provider: Provider, config_cls, client_cls)` so
      external code can plug in adapters without editing the library.
- [ ] Cover with a test that registers a fake provider and round-trips
      through `TrackerClient`.

Files:
- `src/trackerkit/factory/client_factory.py`
- `src/trackerkit/domain/enums.py` (Provider may need to accept dynamic values)

### POL-5. Decide Python lower bound
Code uses `from datetime import UTC` (3.11+) and modern generics. The
project pins `^3.12`.

- [ ] Either lower to `^3.11` (broader audience) or document the 3.12
      choice in `README.md`.
- [ ] If lowering, run pyright/ruff against 3.11.

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

### POL-7. Remove old `dist/` artifacts
`dist/depensee_tracker_client-*.whl` and `*.tar.gz` linger from the
pre-rename state.

- [ ] Delete the old artifacts. `dist/` is already in `.gitignore`,
      so this is a one-time cleanup.

Files:
- `dist/`

---

## Tooling

### TOOL-1. Ruff configuration
`ruff` is in dev-deps but `pyproject.toml` has no `[tool.ruff]` section.

- [ ] Add `[tool.ruff]` with `target-version = "py312"` and
      `[tool.ruff.lint]` selecting at least `E`, `F`, `I`, `UP`, `B`,
      `SIM`, `RUF`.
- [ ] Run `ruff check --fix` once and review the diff.

Files:
- `pyproject.toml`

### TOOL-2. Pytest configuration
- [ ] Add `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`,
      `testpaths = ["tests"]`, optional `addopts = "-q"`).

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

- A. Minimal fix — `extra="ignore"` in Yandex/Asana auth configs (covered by ARCH-1).
- B. Additive — add `TrackerClient.from_config(config: ProviderAuthConfig)` next to the existing constructor.
- C. Breaking — single constructor `TrackerClient(auth_config: ProviderAuthConfig, relation_mapping=None)`, bump to 0.3.0.

- [?] Pick A, B, or C before reworking the facade beyond ARCH-1.

### DEC-2. Shape of `Relation.id`
Today `Relation.id: str | None` is an opaque dispatch token whose
format is parsed by Jira (`jira-contains:<src>:<dst>` or raw link id)
and Yandex (`<issue_id>:<link_id>`). This makes external persistence
fragile.

Options from chat history:
- A. Keep `str`, document as opaque, add explicit format versioning.
- B. Introduce `RelationHandle` model with `serialize()`/`deserialize()`
     and accept `RelationHandle | str` in delete/update.
- C. Drop dispatch tokens entirely — `delete_relation` accepts a
     `DeleteRelationInput(source_task_id, target_task_id, relation_type)`,
     symmetric with `Create/UpdateRelationInput`.

- [?] Pick A, B, or C before reworking relation CRUD beyond CORR-3.

---

## Suggested Execution Order

### Phase A — close 0.3.x maintenance

1. SEC-1 (manual token hygiene).
2. TEST-2, TEST-3, TEST-4; finish TEST-5 contract skeleton.
3. ARCH-1, ARCH-3, ARCH-4; CORR-1..3, PERF-2..4 where still open.
4. TOOL-3, TOOL-4 (CI + pre-commit).
5. Resolve DEC-1 (minimal: `from_config` + `extra="ignore"`) and DEC-2 before 0.3.0 feature work.

PERF-1 and TEST-1 are done.

### Phase B — ship 0.3.0 (see `ROADMAP.md`)

1. Structured errors + `RateLimitError`.
2. Shared rate limiter on provider transports.
3. `TrackerClient.from_config()`.
4. `UserCapability` + `WebhookCapability` (Jira, Yandex Tracker).
5. Relation tests locked under DEC-2.

### Phase C — 0.4.0 / 0.5.0

1. Custom fields + Jira transitions API (0.4.0).
2. Comments (0.4.0).
3. Bulk, OAuth, token hook, POL-6 capability matrix (0.5.0).
