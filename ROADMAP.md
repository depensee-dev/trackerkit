# Roadmap

`trackerkit` is a unified async client for task trackers.
The main product goal is to expose one stable task/project/relation contract
while hiding provider SDK and HTTP details from the host backend (Depensee).

**Last updated:** 2026-11-11 — GitHub Issues shipped in 0.4.0 and replaced
the removed Asana adapter.

Jira, Yandex Tracker, and GitHub are the maintained providers.

Engineering tasks (tests, perf, encapsulation): [`TECH_ROADMAP.md`](TECH_ROADMAP.md).

---

## At a glance

Released so far: **0.3.0** (stabilization), **0.3.1** and **0.3.2** (Yandex
Tracker fixes), **0.4.0** (GitHub Issues; Asana removal), **0.4.1** (canonical
priority and work type). Version numbers below are deliberately not assigned to future stages.

| Stage | Theme | Main deliverables |
| --- | --- | --- |
| **Now** | Stabilization | Relation tests, CI, facade cleanup — see Maintenance |
| **Next** | Real-time sync | Webhooks, rate limit, errors, users API, `from_config()` |
| **Later** | CPM / PERT data | Custom fields, Jira transitions, comments |
| **Someday** | Scale & auth | Bulk, OAuth, token hook, capability matrix |

### High priority (7)

1. Webhooks  
4. Custom fields  
6. Users API  
8. Jira transitions  
9. Rate limiting  
10. Structured errors  
20. `TrackerClient.from_config()`

### Medium (6)

2. Bulk · 5. Comments · 13. OAuth · 14. Token hook · 15. GitHub bulk relation sync · 21. Capability matrix

### Low (9) · Won't (1)

Backlog below · **#22 Sync facade** — out of scope

---

## Priority legend

| Level | Meaning |
| --- | --- |
| **High** | Target for the Next / Later stages |
| **Medium** | Someday, or earlier when unblocked |
| **Low** | Backlog; on demand |
| **Won't** | Not in library scope |

## Feature priorities (items 1–22)

| # | Feature | Priority | Stage |
| --- | --- | --- | --- |
| 1 | Webhooks (register, parse, verify) | **High** | Next |
| 2 | Bulk create/update | Medium | Someday |
| 3 | Task version / `if_match` / `ConflictError` | Low | Backlog |
| 4 | Custom fields | **High** | Later |
| 5 | Comments (list, create) | Medium | Later |
| 6 | Users API (search, by email, self) | **High** | Next |
| 7 | Attachments | Low | Backlog |
| 8 | Jira transitions API | **High** | Later |
| 9 | Rate limiting (token bucket, Retry-After) | **High** | Next |
| 10 | Structured errors + `provider_payload` | **High** | Next |
| 11 | Logging / OpenTelemetry hooks | Low | Backlog |
| 12 | `RetryPolicy` (backoff, retry_on) | Low | Backlog |
| 13 | OAuth 2.0 + refresh | Medium | Someday |
| 14 | `on_token_expired` hook | Medium | Someday |
| 15 | GitHub bulk relation sync | Medium | Someday |
| 16 | Yandex `delete_task` | Low | Backlog |
| 17 | Agile (sprints / epics / boards) | Low | Backlog |
| 18 | VCR / respx integration tests | Low | Backlog |
| 19 | SemVer / CHANGELOG discipline | Low | Ongoing (since 0.3.0) |
| 20 | `TrackerClient.from_config()` / typed entry | **High** | Next |
| 21 | Capability matrix + `supports()` | Medium | Someday |
| 22 | Sync `TrackerClient` wrapper | **Won't** | — |

**Host responsibilities (not trackerkit):** webhook HTTP endpoint, OAuth redirect UI, vault, bidirectional merge policy, PERT field mapping values.

---

## Stage targets

### Next — Real-time sync foundation

Lets Depensee replace scheduled tracker polling with provider events and
handle API limits safely.

**Suggested order inside the release:**

1. Structured errors + `RateLimitError` (foundation for limiter and hosts)  
2. Per-provider rate limiter (`Retry-After`, configurable RPS/burst)  
3. `TrackerClient.from_config()` (DEC-1 minimal path; see `TECH_ROADMAP.md`)
4. `UserCapability` for Jira, Yandex Tracker, and GitHub
5. `WebhookCapability` for Jira, Yandex Tracker, and GitHub
6. Relation CRUD tests + relation ID decision (DEC-2)

**Checklist:**

- [ ] Error taxonomy: `ConflictError`, `RateLimitError`, `ValidationError`; `provider_payload` on all `TrackerKitError` subclasses
- [ ] Per-provider rate limiter; respect `Retry-After` / provider reset headers
- [ ] `TrackerClient.from_config(ProviderAuthConfig)` alongside existing `dict` constructor
- [ ] `UserCapability`: `search`, `get_by_email`, `get_self` (maintained providers)
- [ ] `WebhookCapability`: register, `parse_event`, `verify_signature` (maintained providers)
- [ ] Relation CRUD tests and relation ID semantics (`TECH_ROADMAP.md` TEST-2, TEST-5, DEC-2)

### Later — Integration data (CPM / PERT)

**Checklist:**

- [ ] `Task.custom_fields` + `list_custom_fields(project)` (Jira, Yandex Tracker)
- [ ] Jira `TaskTransitionCapability`: `list_transitions`, `apply_transition` (resolution / extra fields)
- [ ] Comments: `list_comments`, `create_comment` (maintained providers)

### Someday — Scale and enterprise auth

**Checklist:**

- [ ] `bulk_create` / `bulk_update` (Jira bulk API; Yandex concurrent batching under shared rate limiter)
- [ ] GitHub bulk relation loading to avoid per-issue REST fan-out on large boards
- [ ] GitHub App installation-token support and token refresh
- [ ] `AuthProvider`: static token + OAuth2 refresh (library); OAuth UI stays in host
- [ ] Optional `on_token_expired` callback for external secret stores
- [ ] README capability matrix (operations × provider) + runtime `supports(capability)` (POL-6)

### Backlog (low)

- Task version / optimistic concurrency (`if_match` on update)
- Logging / OpenTelemetry hooks on HTTP transport
- Configurable `RetryPolicy` (extends today’s Jira-only `max_retries`)
- Attachments (upload / download / list)
- Yandex `delete_task` policy (API exists; adapter currently rejects)
- GitHub issue deletion through a separate explicitly permissioned workflow
- Jira agile contract (sprints / epics / boards), capability-gated
- VCR / respx snapshot tests

### Won't do

- Sync `TrackerClient` wrapper — hosts use `asyncio` or `anyio.from_thread` themselves

---

## Current status (0.4.1)

### Done

- Public async `TrackerClient` facade for one selected provider, with explicit close / async context-manager lifecycle.
- Typed auth configs (`JiraAuthConfig`, `YandexTrackerAuthConfig`, `GitHubAuthConfig`).
- Shared domain models: workspaces, projects, tasks, statuses, users, comments, relations.
- Canonical optional task priority and work type with exact per-provider mappings for Jira, Yandex Tracker, and GitHub.
- Task CRUD + assignee on read/write where supported; documented provider capability errors for unsupported deletion and due dates.
- Jira, Yandex Tracker, and GitHub relation CRUD (`relates`, `blocks`, `contains`).
- GitHub repository-backed projects, issue read/create/update/count, stable task/relation handles, pagination, pull-request filtering, and bounded concurrency.
- Configurable Jira relation mapping (`RelationMappingConfig`).
- Connection check caching; Jira JQL escaping; Yandex server-side `list_tasks` filters.
- SemVer + `CHANGELOG.md` with Breaking sections.
- Unit tests for mappers, queries, relation policies, GitHub transport and client behavior (see `TECH_ROADMAP.md`).

### Partially done / documented gaps

- **Users / comments:** models and contracts exist; adapters raise `ProviderCapabilityError`.
- **Capability matrix:** partial table in `docs/relations.md` (relations/users/comments only).
- **Rate limits:** Jira SDK `max_retries` and GitHub bounded concurrency/error details exist; no shared limiter or automatic `Retry-After` policy.
- **GitHub relation scale:** native reads are per issue; bulk/GraphQL loading remains future work.
- **GitHub auth:** personal and OAuth user tokens are supported; installation-token discovery remains future work.

### Validated manually

- Yandex Tracker: four tasks, three relation types from a root task.
- Jira (`jira.evt-s.ru`): same, with custom `contains` link mapping when configured.
- GitHub (`depensee-dev/trackerkit`): read-only validation of connection, repository discovery, issue count/list/get, and relation reads on existing issues; native `contains` relations were read from both sides. Issue `#4` also verified as canonical `priority=high`, `work_type=bug`. No GitHub data was modified.

---

## Design principles

- Primary configuration path: explicit config objects → `TrackerClient` (moving to `from_config()` in the Next stage).
- Environment variables only in examples/tests when the host opts in.
- Public relation taxonomy stays small: `relates`, `blocks`, `contains`.
- Provider-specific link types (duplicates, clones, epics) are not public `RelationType` values.
- Unsupported operations → `ProviderCapabilityError`, not raw SDK exceptions.

---

## Maintenance (Now)

Parallel engineering work before / during the Next stage:

| Area | Reference |
| --- | --- |
| Relation + contract tests | `TECH_ROADMAP.md` TEST-2, TEST-5 |
| Facade / auth cleanup | ARCH-1, DEC-1 |
| Examples without private API leaks | ARCH-3 |
| CI / pre-commit | TOOL-3, TOOL-4 |
| SEC-1 token hygiene | manual |

---

## Future providers

New providers (**Bitrix24**, **Trello**, …) after the **Someday** stage unless demand reprioritizes.

Later: Kaiten, YouGile, Planfix, WEEEK, GitLab Issues, Linear, ClickUp.

---

## Explicitly not planned

- Full provider-native relation taxonomy in the public model.
- Automatic `.env` loading inside the library.
- Provider SDK types in public return models.
- Silent fallbacks for unsupported capabilities.
- Webhook HTTP server, OAuth UI, vault, bidirectional merge engine in the library.
