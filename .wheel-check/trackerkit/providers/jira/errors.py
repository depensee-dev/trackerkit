from jira.exceptions import JIRAError

from trackerkit.domain.errors import AuthenticationError, ProviderCapabilityError, ProviderError


def raise_jira_error(error: JIRAError) -> None:
    message = error.text or "Unknown Jira error."

    if error.status_code in (401, 403):
        raise AuthenticationError(
            f"Jira authentication failed or access was denied (HTTP {error.status_code}): {message}"
        ) from error

    if error.status_code == 404:
        raise ProviderError(f"Jira resource was not found: {message}") from error

    raise ProviderError(
        f"Jira request failed (HTTP {error.status_code}): {message}"
    ) from error


def raise_jira_project_creation_error(error: RuntimeError) -> None:
    message = str(error)
    if "issueSecurityScheme" in message or "permissionScheme" in message:
        raise ProviderCapabilityError(
            "Jira project creation requires project scheme access or Jira admin permissions on this instance."
        ) from error
    raise ProviderError(message) from error

