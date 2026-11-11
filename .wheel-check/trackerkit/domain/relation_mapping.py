import os
from collections.abc import Mapping
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from trackerkit.domain.enums import RelationType
from trackerkit.domain.errors import ConfigurationError


class JiraContainsMode(str, Enum):
    STRUCTURAL_HIERARCHY = "structural_hierarchy"
    CUSTOM_LINK_MAPPING = "custom_link_mapping"
    HYBRID = "hybrid"


class JiraLinkTypeMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    relation_type: RelationType
    type_name: str
    outward_label: str | None = None
    inward_label: str | None = None


class JiraRelationMappingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    link_mappings: tuple[JiraLinkTypeMapping, ...] = Field(
        default_factory=lambda: (
            JiraLinkTypeMapping(
                relation_type=RelationType.RELATES,
                type_name="Relates",
                outward_label="relates to",
                inward_label="relates to",
            ),
            JiraLinkTypeMapping(
                relation_type=RelationType.BLOCKS,
                type_name="Blocks",
                outward_label="blocks",
                inward_label="is blocked by",
            ),
        )
    )
    contains_mode: JiraContainsMode = JiraContainsMode.STRUCTURAL_HIERARCHY
    contains_link_mappings: tuple[JiraLinkTypeMapping, ...] = ()

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "JiraRelationMappingConfig":
        """Build optional Jira relation mapping from an explicit env-like source.

        This is an opt-in helper for examples, tests, or host applications that
        intentionally use environment-based settings. The primary integration
        path is constructing `JiraRelationMappingConfig` explicitly and passing
        it into `TrackerClient`.
        """

        source = os.environ if environ is None else environ
        default_config = cls()

        link_mappings = cls._merge_link_mappings(
            default_config.link_mappings,
            (
                cls._read_link_mappings(
                    source,
                    "JIRA_RELATES_LINK_TYPES",
                    RelationType.RELATES,
                )
                or (),
                cls._read_link_mappings(
                    source,
                    "JIRA_BLOCKS_LINK_TYPES",
                    RelationType.BLOCKS,
                )
                or (),
            ),
        )
        contains_link_mappings = cls._read_link_mappings(
            source,
            "JIRA_CONTAINS_LINK_TYPES",
            RelationType.CONTAINS,
        )

        contains_mode_value = source.get(
            "JIRA_CONTAINS_MODE",
            default_config.contains_mode.value,
        )
        try:
            contains_mode = JiraContainsMode(contains_mode_value)
        except ValueError as error:
            raise ConfigurationError(
                "JIRA_CONTAINS_MODE must be one of: "
                f"{', '.join(mode.value for mode in JiraContainsMode)}."
            ) from error
        if contains_link_mappings and "JIRA_CONTAINS_MODE" not in source:
            contains_mode = JiraContainsMode.CUSTOM_LINK_MAPPING

        return cls(
            link_mappings=link_mappings,
            contains_mode=contains_mode,
            contains_link_mappings=contains_link_mappings
            or default_config.contains_link_mappings,
        )

    @classmethod
    def _merge_link_mappings(
        cls,
        defaults: tuple[JiraLinkTypeMapping, ...],
        overrides: tuple[tuple[JiraLinkTypeMapping, ...], ...],
    ) -> tuple[JiraLinkTypeMapping, ...]:
        merged = list(defaults)
        for override_group in overrides:
            if not override_group:
                continue
            relation_type = override_group[0].relation_type
            merged = [
                mapping
                for mapping in merged
                if mapping.relation_type is not relation_type
            ]
            merged.extend(override_group)
        return tuple(merged)

    @classmethod
    def _read_link_mappings(
        cls,
        source: Mapping[str, str],
        env_name: str,
        relation_type: RelationType,
    ) -> tuple[JiraLinkTypeMapping, ...]:
        value = source.get(env_name)
        if value is None or value.strip() == "":
            return ()

        mappings: list[JiraLinkTypeMapping] = []
        for item in value.split(";"):
            item = item.strip()
            if not item:
                continue
            parts = [part.strip() for part in item.split("|")]
            if len(parts) not in {1, 3} or any(part == "" for part in parts):
                raise ConfigurationError(
                    f"{env_name} must use 'type_name' or "
                    "'type_name|outward_label|inward_label' entries separated by ';'."
                )
            type_name = parts[0]
            outward_label = parts[1] if len(parts) == 3 else None
            inward_label = parts[2] if len(parts) == 3 else None
            mappings.append(
                JiraLinkTypeMapping(
                    relation_type=relation_type,
                    type_name=type_name,
                    outward_label=outward_label,
                    inward_label=inward_label,
                )
            )
        return tuple(mappings)


class YandexTrackerRelationMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    relation_type: RelationType
    outward_value: str
    inward_value: str


class YandexTrackerRelationMappingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mappings: tuple[YandexTrackerRelationMapping, ...] = Field(
        default_factory=lambda: (
            YandexTrackerRelationMapping(
                relation_type=RelationType.RELATES,
                outward_value="relates",
                inward_value="relates",
            ),
            YandexTrackerRelationMapping(
                relation_type=RelationType.BLOCKS,
                outward_value="is dependent by",
                inward_value="depends on",
            ),
            YandexTrackerRelationMapping(
                relation_type=RelationType.CONTAINS,
                outward_value="is parent task for",
                inward_value="is subtask for",
            ),
        )
    )


class RelationMappingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    jira: JiraRelationMappingConfig = Field(default_factory=JiraRelationMappingConfig)
    yandex_tracker: YandexTrackerRelationMappingConfig = Field(
        default_factory=YandexTrackerRelationMappingConfig
    )

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "RelationMappingConfig":
        """Build optional relation mapping from an explicit env-like source.

        Currently only Jira relation mapping keys are supported. This helper is
        opt-in and is not used by `TrackerClient` unless the caller passes its
        result during client initialization.
        """

        return cls(jira=JiraRelationMappingConfig.from_env(environ))
