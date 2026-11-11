"""Tests for `TrackerClient` connection guard behavior.

Covers:
- TEST-5: `_build_connection_error` produces the right normalized error class.
- PERF-1: lazy connection cache and `verify_each_call` semantics.
- POL-2: validation of `connection_timeout`, `max_retries`, `connection_check_ttl`.
"""

from __future__ import annotations

from typing import Any

import pytest

from trackerkit.domain.enums import ConnectionErrorKind, Provider
from trackerkit.domain.errors import (
    AuthenticationError,
    ConfigurationError,
    ProviderError,
)
from trackerkit.domain.models import ConnectionDiagnostic, Task
from trackerkit.tracker_client import TrackerClient


def _build_dummy_client() -> TrackerClient:
    return TrackerClient(
        provider=Provider.GITHUB,
        auth_data={"access_token": "secret"},
    )


def _make_diagnostic(
    *,
    is_connected: bool,
    error_kind: ConnectionErrorKind | None = None,
    message: str | None = None,
) -> ConnectionDiagnostic:
    return ConnectionDiagnostic(
        provider=Provider.GITHUB,
        is_connected=is_connected,
        error_kind=error_kind,
        message=message,
    )


class _StubInner:
    def __init__(self, diagnostics: list[ConnectionDiagnostic]) -> None:
        self.diagnostics = diagnostics
        self.calls = 0
        self.task_calls = 0

    async def get_connection_diagnostic(self) -> ConnectionDiagnostic:
        self.calls += 1
        index = min(self.calls - 1, len(self.diagnostics) - 1)
        return self.diagnostics[index]

    async def get_task(self, task_id: str) -> Task:
        self.task_calls += 1
        return Task(id=task_id, title="t")

    def __getattr__(self, item: str) -> Any:
        async def _missing(*args: Any, **kwargs: Any) -> None:
            raise AssertionError(f"unexpected call to {item}")

        return _missing


class TestBuildConnectionError:
    def test_authentication_kind_yields_authentication_error(self) -> None:
        client = _build_dummy_client()
        err = client._build_connection_error(
            _make_diagnostic(
                is_connected=False,
                error_kind=ConnectionErrorKind.AUTHENTICATION,
                message="bad token",
            )
        )
        assert isinstance(err, AuthenticationError)
        assert "bad token" in str(err)

    def test_configuration_kind_yields_configuration_error(self) -> None:
        client = _build_dummy_client()
        err = client._build_connection_error(
            _make_diagnostic(
                is_connected=False,
                error_kind=ConnectionErrorKind.CONFIGURATION,
            )
        )
        assert isinstance(err, ConfigurationError)

    def test_provider_kind_yields_provider_error(self) -> None:
        client = _build_dummy_client()
        err = client._build_connection_error(
            _make_diagnostic(
                is_connected=False,
                error_kind=ConnectionErrorKind.PROVIDER,
            )
        )
        assert isinstance(err, ProviderError)

    def test_capability_kind_falls_back_to_provider_error(self) -> None:
        client = _build_dummy_client()
        err = client._build_connection_error(
            _make_diagnostic(
                is_connected=False,
                error_kind=ConnectionErrorKind.CAPABILITY,
            )
        )
        assert isinstance(err, ProviderError)

    def test_unknown_kind_uses_default_message(self) -> None:
        client = _build_dummy_client()
        err = client._build_connection_error(_make_diagnostic(is_connected=False, error_kind=None))
        assert isinstance(err, ProviderError)
        assert "github" in str(err).lower()


class TestConnectionTtlCache:
    @pytest.mark.asyncio
    async def test_cache_avoids_repeat_provider_calls(self) -> None:
        client = _build_dummy_client()
        stub = _StubInner([_make_diagnostic(is_connected=True)])
        client._client = stub  # type: ignore[assignment]

        await client.get_task("T1")
        await client.get_task("T2")
        await client.get_task("T3")

        assert stub.calls == 1
        assert stub.task_calls == 3

    @pytest.mark.asyncio
    async def test_verify_each_call_disables_cache(self) -> None:
        client = TrackerClient(
            provider=Provider.GITHUB,
            auth_data={"access_token": "secret"},
            verify_each_call=True,
        )
        stub = _StubInner([_make_diagnostic(is_connected=True)])
        client._client = stub  # type: ignore[assignment]

        await client.get_task("T1")
        await client.get_task("T2")

        assert stub.calls == 2

    @pytest.mark.asyncio
    async def test_zero_ttl_disables_cache(self) -> None:
        client = TrackerClient(
            provider=Provider.GITHUB,
            auth_data={"access_token": "secret"},
            connection_check_ttl=0.0,
        )
        stub = _StubInner([_make_diagnostic(is_connected=True)])
        client._client = stub  # type: ignore[assignment]

        await client.get_task("T1")
        await client.get_task("T2")

        assert stub.calls == 2

    @pytest.mark.asyncio
    async def test_invalidate_cache_forces_reverify(self) -> None:
        client = _build_dummy_client()
        stub = _StubInner([_make_diagnostic(is_connected=True)])
        client._client = stub  # type: ignore[assignment]

        await client.get_task("T1")
        client.invalidate_connection_cache()
        await client.get_task("T2")

        assert stub.calls == 2

    @pytest.mark.asyncio
    async def test_failed_check_does_not_populate_cache(self) -> None:
        client = _build_dummy_client()
        stub = _StubInner(
            [
                _make_diagnostic(
                    is_connected=False,
                    error_kind=ConnectionErrorKind.AUTHENTICATION,
                    message="bad",
                ),
                _make_diagnostic(is_connected=True),
            ]
        )
        client._client = stub  # type: ignore[assignment]

        with pytest.raises(AuthenticationError):
            await client.get_task("T1")
        await client.get_task("T2")

        assert stub.calls == 2


class TestInitValidation:
    def test_negative_timeout_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            TrackerClient(
                provider=Provider.GITHUB,
                auth_data={"access_token": "secret"},
                connection_timeout=0,
            )

    def test_negative_retries_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            TrackerClient(
                provider=Provider.GITHUB,
                auth_data={"access_token": "secret"},
                max_retries=-1,
            )

    def test_negative_ttl_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            TrackerClient(
                provider=Provider.GITHUB,
                auth_data={"access_token": "secret"},
                connection_check_ttl=-1,
            )
