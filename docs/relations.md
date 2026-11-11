# Relations

## Signature
```python
await client.list_relations(task_id: str) -> list[Relation]
await client.create_relation(payload: CreateRelationInput) -> Relation
await client.update_relation(relation_id: str, payload: UpdateRelationInput) -> Relation
await client.delete_relation(relation_id: str) -> None
```

## Core Relation Types
The product-facing relation model is intentionally smaller than provider-native link systems.

- `relates` - weak semantic connection without strict dependency
- `blocks` - directed blocking dependency where `source_task_id` blocks `target_task_id`
- `contains` - structural parent-child relation where `source_task_id` contains `target_task_id`

These relation types fit the visual graph model of the product:
- tasks are nodes
- relations are edges
- node appearance may vary by task type
- edge appearance may vary by relation type

Provider-specific relation variants such as duplicates, clones, epics, or custom
hierarchy levels are intentionally outside the public `RelationType` enum.

## Models
```python
class Relation(BaseModel):
    id: str | None = None
    source_task_id: str
    target_task_id: str
    relation_type: RelationType


class CreateRelationInput(BaseModel):
    source_task_id: str
    target_task_id: str
    relation_type: RelationType


class UpdateRelationInput(BaseModel):
    source_task_id: str
    target_task_id: str
    relation_type: RelationType
```

## Default Provider Mapping
| Shared relation | Jira default | Yandex Tracker default | GitHub |
| --- | --- | --- | --- |
| `relates` | issue link type `Relates` | native `relates` link | native `relates_to` |
| `blocks` | issue link type `Blocks` | native `is dependent by` / `depends on` | native `blocked by` / `blocking` dependency |
| `contains` | structural hierarchy (`parent` / `subtask`) | native `is parent task for` / `is subtask for` | native parent issue / sub-issues |

## Relation Mapping Config
Use `RelationMappingConfig` when Jira or Yandex defaults are not enough.
GitHub uses fixed native semantics and does not need relation-label mapping.

```python
from trackerkit import (
    JiraContainsMode,
    JiraLinkTypeMapping,
    JiraRelationMappingConfig,
    RelationMappingConfig,
    RelationType,
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
```

The primary path is to pass `RelationMappingConfig` explicitly during client
initialization. For examples, tests, or host services that intentionally use
environment-based settings, you can build the same optional Jira mapping from
environment variables:

```python
from trackerkit import RelationMappingConfig, TrackerClient

client = TrackerClient(
    provider="jira",
    auth_data={...},
    relation_mapping=RelationMappingConfig.from_env(),
)
```

Supported Jira env variables:
- `JIRA_RELATES_LINK_TYPES`
- `JIRA_BLOCKS_LINK_TYPES`
- `JIRA_CONTAINS_LINK_TYPES`
- `JIRA_CONTAINS_MODE`

`*_LINK_TYPES` values can use the simple type-name format:

```text
Type name;Another type
```

For stricter matching, include Jira direction labels:

```text
JIRA_BLOCKS_LINK_TYPES=Blocks|blocks|is blocked by
```

When `JIRA_CONTAINS_LINK_TYPES` is set and `JIRA_CONTAINS_MODE` is not set,
`contains` uses `custom_link_mapping` so relation create/delete can use Jira issue links.

### Jira modes
- `structural_hierarchy` - default mode; `contains` is read and created through hierarchy, not through issue links
- `custom_link_mapping` - `contains` is handled only through configured link types
- `hybrid` - read both hierarchy and configured custom link types; create uses hierarchy first

## CRUD Behavior Notes
### Jira
- `relates` and `blocks` use issue link CRUD
- `contains` defaults to hierarchy by setting the child issue parent
- deleting a structural `contains` relation is intentionally blocked because safe generic parent removal is not reliable across Jira setups
- for full CRUD for `contains`, use `custom_link_mapping` or `hybrid` with a dedicated custom link type

### Yandex Tracker
- all three core relation types use native issue links
- `create_relation()` always creates the provider-native outward value from `source_task_id` to `target_task_id`
- `update_relation()` is modeled as replace: delete old link, create new link

### GitHub
- `relates` uses list/add/remove operations on `/relates_to`; the relation is symmetric, so the adapter canonicalizes endpoint order by global issue ID to avoid duplicate reverse edges
- `blocks` uses `/dependencies/blocked_by` and `/dependencies/blocking`; for `source blocks target`, the adapter adds the source as a `blocked_by` dependency of the target
- `contains` uses parent, `/sub_issues`, and `/sub_issue` endpoints; the source is the parent and the target is the sub-issue
- adding a sub-issue never silently replaces an existing parent (`replace_parent=False`); GitHub requires both issues to belong to the same repository owner
- relation IDs are opaque, versioned handles containing both task handles and relation type; host code must not parse them
- `update_relation()` is modeled as delete + create
- a full relation read fans out to the native related/dependency/hierarchy endpoints; use bounded concurrency and avoid unnecessary polling

## Provider Capability Summary
| Provider | Relations | Users | Comments |
| --- | --- | --- | --- |
| Jira | implemented for core relation types | not implemented | not implemented |
| Yandex Tracker | implemented for core relation types | not implemented | not implemented |
| GitHub | implemented for core relation types | not implemented | not implemented |

## Sources
- GitHub: [Issues and related issues](https://docs.github.com/en/rest/issues/issues)
- GitHub: [Issue dependencies](https://docs.github.com/en/rest/issues/issue-dependencies)
- GitHub: [Sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
- GitHub: [REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

## Example
```python
from trackerkit import (
    CreateRelationInput,
    RelationType,
    TrackerClient,
    UpdateRelationInput,
)

async with TrackerClient(
    provider="github",
    auth_data={"access_token": "secret"},
) as client:
    relations = await client.list_relations(task_id="github-task-handle")

    created = await client.create_relation(
        CreateRelationInput(
            source_task_id="github-source-handle",
            target_task_id="github-target-handle",
            relation_type=RelationType.BLOCKS,
        )
    )

    updated = await client.update_relation(
        created.id,
        UpdateRelationInput(
            source_task_id="github-source-handle",
            target_task_id="github-other-target-handle",
            relation_type=RelationType.BLOCKS,
        ),
    )

    await client.delete_relation(updated.id)
```
