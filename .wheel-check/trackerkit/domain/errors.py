from trackerkit.domain.enums import ConnectionErrorKind


class TrackerClientError(Exception):
    """Base exception for the package."""


class ConfigurationError(TrackerClientError):
    """Raised when client configuration is invalid."""


class AuthenticationError(TrackerClientError):
    """Raised when provider authentication fails."""


class ProviderError(TrackerClientError):
    """Raised when a provider-specific operation fails."""


class ProviderCapabilityError(TrackerClientError):
    """Raised when a provider does not support a requested capability."""


TrackerKitError = TrackerClientError


def get_error_kind(error: Exception) -> ConnectionErrorKind:
    if isinstance(error, AuthenticationError):
        return ConnectionErrorKind.AUTHENTICATION
    if isinstance(error, ConfigurationError):
        return ConnectionErrorKind.CONFIGURATION
    if isinstance(error, ProviderCapabilityError):
        return ConnectionErrorKind.CAPABILITY
    if isinstance(error, ProviderError):
        return ConnectionErrorKind.PROVIDER
    return ConnectionErrorKind.PROVIDER

