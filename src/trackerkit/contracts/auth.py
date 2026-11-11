from pydantic import BaseModel, ConfigDict, Field, model_validator

from trackerkit.domain.enums import Provider
from trackerkit.domain.errors import ConfigurationError


class ProviderAuthConfig(BaseModel):
    """Base auth config shared by all provider-specific auth models."""

    # `extra="ignore"` lets the facade pass provider-agnostic kwargs
    # (e.g. `max_retries`) without leaking provider checks into it.
    model_config = ConfigDict(frozen=True, extra="ignore")

    provider: Provider
    timeout_seconds: float = Field(default=5.0, gt=0)


class JiraAuthConfig(ProviderAuthConfig):
    """Jira auth data.

    Expected fields:
    - `base_url`
    - exactly one of `access_token` or `api_token`
    - optional `max_retries`
    """

    provider: Provider = Provider.JIRA
    base_url: str
    email: str | None = None
    api_token: str | None = None
    access_token: str | None = None
    max_retries: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def validate_auth(self) -> "JiraAuthConfig":
        if not self.api_token and not self.access_token:
            raise ConfigurationError("JiraAuthConfig requires either api_token or access_token.")
        if self.api_token and self.access_token:
            raise ConfigurationError(
                "JiraAuthConfig expects only one of api_token or access_token."
            )
        return self


class YandexTrackerAuthConfig(ProviderAuthConfig):
    """Yandex Tracker auth data.

    Expected fields:
    - exactly one of `token` or `iam_token`
    - exactly one of `org_id` or `cloud_org_id`
    """

    provider: Provider = Provider.YANDEX_TRACKER
    token: str | None = None
    iam_token: str | None = None
    org_id: str | None = None
    cloud_org_id: str | None = None

    @model_validator(mode="after")
    def validate_auth(self) -> "YandexTrackerAuthConfig":
        if not self.token and not self.iam_token:
            raise ConfigurationError("YandexTrackerAuthConfig requires either token or iam_token.")
        if self.token and self.iam_token:
            raise ConfigurationError(
                "YandexTrackerAuthConfig expects only one of token or iam_token."
            )
        if not self.org_id and not self.cloud_org_id:
            raise ConfigurationError(
                "YandexTrackerAuthConfig requires either org_id or cloud_org_id."
            )
        if self.org_id and self.cloud_org_id:
            raise ConfigurationError(
                "YandexTrackerAuthConfig expects only one of org_id or cloud_org_id."
            )
        return self


class GitHubAuthConfig(ProviderAuthConfig):
    """GitHub auth data for a personal or OAuth user access token."""

    provider: Provider = Provider.GITHUB
    access_token: str = Field(min_length=1)
    base_url: str = "https://api.github.com"
    api_version: str = "2026-03-10"
    max_concurrency: int = Field(default=10, ge=1, le=100)
