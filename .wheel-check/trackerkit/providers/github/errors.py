import httpx

from trackerkit.domain.errors import AuthenticationError, ProviderError


class GitHubNotFoundError(ProviderError):
    pass


def raise_github_error(response: httpx.Response, method: str, path: str) -> None:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    message = payload.get("message") if isinstance(payload, dict) else None
    detail = message or response.text[:500] or "GitHub API request failed."
    error_message = f"GitHub API {method} {path} returned {response.status_code}: {detail}"
    if response.status_code in {403, 429}:
        retry_after = response.headers.get("retry-after")
        reset = response.headers.get("x-ratelimit-reset")
        if retry_after:
            error_message = f"{error_message}; retry after {retry_after} seconds"
        elif reset:
            error_message = f"{error_message}; rate limit resets at Unix timestamp {reset}"
    if response.status_code == 401:
        raise AuthenticationError(error_message)
    if response.status_code == 404:
        raise GitHubNotFoundError(error_message)
    raise ProviderError(error_message)
