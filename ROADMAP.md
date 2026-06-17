# Roadmap

`trackerkit` is a unified async client for task trackers.
The main product goal is to expose one stable task/project/relation contract
while hiding provider SDK details from the host backend (e.g. ChainForge).

**Last updated:** 2026-05-21 — priorities from integration review (items 1–22).

Engineering tasks (tests, perf, encapsulation): [`TECH_ROADMAP.md`](TECH_ROADMAP.md).

---

## At a glance

| Release | Theme | Main deliverables |
| --- | --- | --- |
| **0.3.x** (current) | Stabilization | Relation tests, CI, facade cleanup — see Maintenance |
| **0.3.0** | Real-time sync | Webhooks, rate limit, errors, users API, `from_config()` |
| **0.4.0** | CPM / PERT data | Custom fields, Jira transitions, comments |
| **0.5.0** | Scale & auth | Bulk, OAuth, token hook, capability matrix |

### High priority (7)

1. Webhooks  
4. Custom fields  
6. Users API  
8. Jira transitions  
9. Rate limiting  
10. Structured errors  
20. `TrackerClient.from_config()`

### Medium (5)

2. Bulk · 5. Comments · 13. OAuth · 14. Token hook · 21. Capability matrix

### Low (10) · Won't (1)

Backlog below · **#22 Sync facade** — out of scope

---

## Priority legend

| Level | Meaning |
| --- | --- |
| **High** | Target for next product releases (0.3–0.4) |
| **Medium** | 0.5.0 or when unblocked |
| **Low** | Backlog; on demand |
| **Won't** | Not in library scope |

## Feature priorities (items 1–22)

| # | Feature | Priority | Release |
| --- | --- | --- | --- |
| 1 | Webhooks (register, parse, verify) | **High** | 0.3.0 |
| 2 | Bulk create/update | Medium | 0.5.0 |
| 3 | Task version / `if_match` / `ConflictError` | Low | Backlog |
| 4 | Custom fields | **High** | 0.4.0 |
| 5 | Comments (list, create) | Medium | 0.4.0 |
| 6 | Users API (search, by email, self) | **High** | 0.3.0 |
| 7 | Attachments | Low | Backlog |
| 8 | Jira transitions API | **High** | 0.4.0 |
| 9 | Rate limiting (token bucket, Retry-After) | **High** | 0.3.0 |
| 10 | Structured errors + `provider_payload` | **High** | 0.3.0 |
| 11 | Logging / OpenTelemetry hooks | Low | Backlog |
| 12 | `RetryPolicy` (backoff, retry_on) | Low | Backlog |
| 13 | OAuth 2.0 + refresh | Medium | 0.5.0 |
| 14 | `on_token_expired` hook | Medium | 0.5.0 |
| 15 | Asana relations | Low | Backlog |
| 16 | Yandex `delete_task` | Low | Backlog |
| 17 | Agile (sprints / epics / boards) | Low | Backlog |
| 18 | VCR / respx integration tests | Low | Backlog |
| 19 | SemVer / CHANGELOG discipline | Low | Ongoing (started 0.3.0) |
| 20 | `TrackerClient.from_config()` / typed entry | **High** | 0.3.0 |
| 21 | Capability matrix + `supports()` | Medium | 0.5.0 |
| 22 | Sync `TrackerClient` wrapper | **Won't** | — |

**Host responsibilities (not trackerkit):** webhook HTTP endpoint, OAuth redirect UI, vault, bidirectional merge policy, PERT field mapping values.

---

## Release targets

### 0.3.0 — Real-time sync foundation

Enables ChainForge to move off Celery polling and handle API limits safely.

**Suggested order inside the release:**

1. Structured errors + `RateLimitError` (foundation for limiter and hosts)  
2. Per-provider rate limiter (`Retry-After`, configurable RPS/burst)  
3. `TrackerClient.from_config()` (DEC-1 minimal path; see `TECH_ROADMAP.md`)  
4. `UserCapability` for Jira and Yandex Tracker  
5. `WebhookCapability` for Jira and Yandex Tracker  
6. Relation CRUD tests + relation ID decision (DEC-2)

**Checklist:**

- [ ] Error taxonomy: `ConflictError`, `RateLimitError`, `ValidationError`; `provider_payload` on all `TrackerKitError` subclasses
- [ ] Per-provider rate limiter; respect `Retry-After` / provider reset headers
- [ ] `TrackerClient.from_config(ProviderAuthConfig)` alongside existing `dict` constructor
- [ ] `UserCapability`: `search`, `get_by_email`, `get_self` (Jira, Yandex Tracker)
- [ ] `WebhookCapability`: register, `parse_event`, `verify_signature` (Jira, Yandex Tracker)
- [ ] Relation CRUD tests and relation ID semantics (`TECH_ROADMAP.md` TEST-2, TEST-5, DEC-2)

### 0.4.0 — Integration data (CPM / PERT)

**Checklist:**

- [ ] `Task.custom_fields` + `list_custom_fields(project)` (Jira, Yandex Tracker)
- [ ] Jira `TaskTransitionCapability`: `list_transitions`, `apply_transition` (resolution / extra fields)
- [ ] Comments: `list_comments`, `create_comment` (Jira, Yandex Tracker)

### 0.5.0 — Scale and enterprise auth

**Checklist:**

- [ ] `bulk_create` / `bulk_update` (Jira bulk API; Yandex concurrent batching under shared rate limiter)
- [ ] `AuthProvider`: static token + OAuth2 refresh (library); OAuth UI stays in host
- [ ] Optional `on_token_expired` callback for external secret stores
- [ ] README capability matrix (operations × provider) + runtime `supports(capability)` (POL-6)

### Backlog (low)

- Task version / optimistic concurrency (`if_match` on update)
- Logging / OpenTelemetry hooks on HTTP transport
- Configurable `RetryPolicy` (extends today’s Jira-only `max_retries`)
- Attachments (upload / download / list)
- Asana relations (dependencies → `blocks`, subtasks → `contains`)
- Yandex `delete_task` policy (API exists; adapter currently rejects)
- Jira agile contract (sprints / epics / boards), capability-gated
- VCR / respx snapshot tests

### Won't do

- Sync `TrackerClient` wrapper — hosts use `asyncio` or `anyio.from_thread` themselves

---

## Current status (0.3.0)

### Done

- Public async `TrackerClient` facade for one selected provider.
- Typed auth configs (`JiraAuthConfig`, `YandexTrackerAuthConfig`, `AsanaAuthConfig`).
- Shared domain models: workspaces, projects, tasks, statuses, users, comments, relations.
- Task CRUD + assignee on read/write (`assignee_id`); Jira uses internal transitions when `status_id` is set.
- Jira and Yandex Tracker relation CRUD (`relates`, `blocks`, `contains`).
- Configurable Jira relation mapping (`RelationMappingConfig`).
- Connection check caching; Jira JQL escaping; Yandex server-side `list_tasks` filters.
- SemVer + `CHANGELOG.md` with Breaking sections.
- Unit tests for mappers, queries, relation policies (see `TECH_ROADMAP.md`).

### Partially done / documented gaps

- **Users / comments:** models and contracts exist; adapters raise `ProviderCapabilityError`.
- **Capability matrix:** partial table in `docs/relations.md` (relations/users/comments only).
- **Rate limits:** Jira SDK `max_retries` only; no shared limiter or `Retry-After` handling.

### Validated manually

- Yandex Tracker: four tasks, three relation types from a root task.
- Jira (`jira.evt-s.ru`): same, with custom `contains` link mapping when configured.

---

## Design principles

- Primary configuration path: explicit config objects → `TrackerClient` (moving to `from_config()` in 0.3.0).
- Environment variables only in examples/tests when the host opts in.
- Public relation taxonomy stays small: `relates`, `blocks`, `contains`.
- Provider-specific link types (duplicates, clones, epics) are not public `RelationType` values.
- Unsupported operations → `ProviderCapabilityError`, not raw SDK exceptions.

---

## Maintenance (0.3.x)

Parallel engineering work before / during 0.3.0:

| Area | Reference |
| --- | --- |
| Relation + contract tests | `TECH_ROADMAP.md` TEST-2, TEST-5 |
| Facade / auth cleanup | ARCH-1, DEC-1 |
| Examples without private API leaks | ARCH-3 |
| CI / pre-commit | TOOL-3, TOOL-4 |
| SEC-1 token hygiene | manual |

---

## Future providers

New providers (**Bitrix24**, **Trello**, …) after **0.5.0** unless demand reprioritizes.

Later: Kaiten, YouGile, Planfix, WEEEK, GitHub/GitLab Issues, Linear, ClickUp.

---

## Explicitly not planned

- Full provider-native relation taxonomy in the public model.
- Automatic `.env` loading inside the library.
- Provider SDK types in public return models.
- Silent fallbacks for unsupported capabilities.
- Webhook HTTP server, OAuth UI, vault, bidirectional merge engine in the library.
