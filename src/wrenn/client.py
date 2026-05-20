from __future__ import annotations

import asyncio
import os
import time

import httpx

from wrenn._config import (
    DEFAULT_BASE_URL,
    DEFAULT_PROXY_DOMAIN,
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_PROXY_DOMAIN,
)
from wrenn.exceptions import handle_response

from wrenn.models import (
    Template,
)
from wrenn.models import (
    Capsule as CapsuleModel,
)

_LONG_TIMEOUT = httpx.Timeout(60.0)
_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
)
_RETRY_METHODS = frozenset({"GET", "HEAD", "DELETE", "OPTIONS", "PUT"})
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.3


def _should_retry(request: httpx.Request, attempt: int) -> bool:
    return attempt < _MAX_RETRIES - 1 and request.method.upper() in _RETRY_METHODS


def _backoff_delay(attempt: int) -> float:
    return _BACKOFF_BASE * (2**attempt)


class _RetryingClient(httpx.Client):
    """httpx.Client that retries transient TLS/connection errors on
    idempotent methods (GET/HEAD/DELETE/OPTIONS/PUT). Non-idempotent
    requests (POST/PATCH) propagate immediately."""

    def send(self, request: httpx.Request, **kwargs):  # type: ignore[override]
        for attempt in range(_MAX_RETRIES):
            try:
                return super().send(request, **kwargs)
            except _RETRY_EXCEPTIONS:
                if not _should_retry(request, attempt):
                    raise
                time.sleep(_backoff_delay(attempt))
        # Unreachable: loop either returns or raises.
        raise RuntimeError("retry loop exited without result")


class _RetryingAsyncClient(httpx.AsyncClient):
    """Async variant of :class:`_RetryingClient`."""

    async def send(self, request: httpx.Request, **kwargs):  # type: ignore[override]
        for attempt in range(_MAX_RETRIES):
            try:
                return await super().send(request, **kwargs)
            except _RETRY_EXCEPTIONS:
                if not _should_retry(request, attempt):
                    raise
                await asyncio.sleep(_backoff_delay(attempt))
        raise RuntimeError("retry loop exited without result")


def _resolve_api_key(api_key: str | None) -> str:
    resolved = api_key or os.environ.get(ENV_API_KEY)
    if not resolved:
        raise ValueError(
            f"No API key provided. Pass api_key= or set the {ENV_API_KEY} environment variable."
        )
    return resolved


def _resolve_timeout(
    timeout: httpx.Timeout | float | None,
) -> httpx.Timeout:
    if timeout is None:
        return _DEFAULT_TIMEOUT
    if isinstance(timeout, httpx.Timeout):
        return timeout
    return httpx.Timeout(timeout)


def _resolve_proxy_domain(base_url: str, override: str | None) -> str:
    """Resolve proxy host suffix for ``{port}-{capsule_id}.<domain>`` URLs.

    Precedence: explicit ``override`` arg, ``WRENN_PROXY_DOMAIN`` env, then
    ``wrenn.dev`` only when ``base_url`` is the default Wrenn host
    (``app.wrenn.dev``). Otherwise the ``base_url`` host (with port) is used
    verbatim — appropriate for local dev or custom deployments.
    """
    resolved = override or os.environ.get(ENV_PROXY_DOMAIN)
    if resolved:
        return resolved
    parsed = httpx.URL(base_url)
    host = parsed.host
    if host == "app.wrenn.dev":
        return DEFAULT_PROXY_DOMAIN
    if parsed.port:
        return f"{host}:{parsed.port}"
    return host


def _build_capsule_create_payload(
    template: str | None,
    vcpus: int | None,
    memory_mb: int | None,
    timeout_sec: int | None,
) -> dict:
    payload: dict = {}
    if template is not None:
        payload["template"] = template
    if vcpus is not None:
        payload["vcpus"] = vcpus
    if memory_mb is not None:
        payload["memory_mb"] = memory_mb
    if timeout_sec is not None:
        payload["timeout_sec"] = timeout_sec
    return payload


def _build_snapshot_create(
    capsule_id: str, name: str | None, overwrite: bool
) -> tuple[dict, dict]:
    payload: dict = {"sandbox_id": capsule_id}
    if name is not None:
        payload["name"] = name
    params: dict = {}
    if overwrite:
        params["overwrite"] = "true"
    return payload, params


def _snapshot_list_params(type: str | None) -> dict:
    params: dict = {}
    if type is not None:
        params["type"] = type
    return params


class CapsulesResource:
    """Sync capsule control-plane operations."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout_sec: int | None = None,
    ) -> CapsuleModel:
        """Create a new capsule.

        Args:
            template (str | None): Template name to boot from.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout_sec (int | None): Inactivity TTL in seconds before
                auto-pause. ``0`` disables auto-pause.

        Returns:
            CapsuleModel: The newly created capsule.
        """
        resp = self._http.post(
            "/v1/capsules",
            json=_build_capsule_create_payload(template, vcpus, memory_mb, timeout_sec),
        )
        return CapsuleModel.model_validate(handle_response(resp))

    def list(self) -> list[CapsuleModel]:
        """List all capsules for the authenticated team.

        Returns:
            list[CapsuleModel]: All capsules belonging to the team.
        """
        resp = self._http.get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    def get(self, id: str) -> CapsuleModel:
        """Get a capsule by ID.

        Args:
            id (str): Capsule ID.

        Returns:
            CapsuleModel: Current state of the capsule.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = self._http.get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    def destroy(self, id: str) -> None:
        """Destroy a capsule permanently.

        Args:
            id (str): Capsule ID.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = self._http.delete(f"/v1/capsules/{id}")
        handle_response(resp)

    def pause(self, id: str) -> CapsuleModel:
        """Pause a running capsule.

        Args:
            id (str): Capsule ID.

        Returns:
            CapsuleModel: Updated capsule state.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = self._http.post(f"/v1/capsules/{id}/pause")
        return CapsuleModel.model_validate(handle_response(resp))

    def resume(self, id: str) -> CapsuleModel:
        """Resume a paused capsule.

        Args:
            id (str): Capsule ID.

        Returns:
            CapsuleModel: Updated capsule state.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = self._http.post(f"/v1/capsules/{id}/resume")
        return CapsuleModel.model_validate(handle_response(resp))

    def ping(self, id: str) -> None:
        """Reset the inactivity timer for a capsule.

        Args:
            id (str): Capsule ID.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = self._http.post(f"/v1/capsules/{id}/ping")
        handle_response(resp)


class AsyncCapsulesResource:
    """Async capsule control-plane operations."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def create(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout_sec: int | None = None,
    ) -> CapsuleModel:
        """Create a new capsule.

        Args:
            template (str | None): Template name to boot from.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout_sec (int | None): Inactivity TTL in seconds before
                auto-pause. ``0`` disables auto-pause.

        Returns:
            CapsuleModel: The newly created capsule.
        """
        resp = await self._http.post(
            "/v1/capsules",
            json=_build_capsule_create_payload(template, vcpus, memory_mb, timeout_sec),
        )
        return CapsuleModel.model_validate(handle_response(resp))

    async def list(self) -> list[CapsuleModel]:
        """List all capsules for the authenticated team.

        Returns:
            list[CapsuleModel]: All capsules belonging to the team.
        """
        resp = await self._http.get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    async def get(self, id: str) -> CapsuleModel:
        """Get a capsule by ID.

        Args:
            id (str): Capsule ID.

        Returns:
            CapsuleModel: Current state of the capsule.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = await self._http.get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    async def destroy(self, id: str) -> None:
        """Destroy a capsule permanently.

        Args:
            id (str): Capsule ID.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = await self._http.delete(f"/v1/capsules/{id}")
        handle_response(resp)

    async def pause(self, id: str) -> CapsuleModel:
        """Pause a running capsule.

        Args:
            id (str): Capsule ID.

        Returns:
            CapsuleModel: Updated capsule state.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = await self._http.post(f"/v1/capsules/{id}/pause")
        return CapsuleModel.model_validate(handle_response(resp))

    async def resume(self, id: str) -> CapsuleModel:
        """Resume a paused capsule.

        Args:
            id (str): Capsule ID.

        Returns:
            CapsuleModel: Updated capsule state.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = await self._http.post(f"/v1/capsules/{id}/resume")
        return CapsuleModel.model_validate(handle_response(resp))

    async def ping(self, id: str) -> None:
        """Reset the inactivity timer for a capsule.

        Args:
            id (str): Capsule ID.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        resp = await self._http.post(f"/v1/capsules/{id}/ping")
        handle_response(resp)


class SnapshotsResource:
    """Sync snapshot operations."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create(
        self,
        capsule_id: str,
        name: str | None = None,
        overwrite: bool = False,
    ) -> Template:
        """Create a snapshot template from a running capsule.

        Args:
            capsule_id (str): ID of the capsule to snapshot.
            name (str | None): Name for the snapshot template. Auto-generated
                if not provided.
            overwrite (bool): If ``True``, overwrite an existing template with
                the same name. Defaults to ``False``.

        Returns:
            Template: The created snapshot template.
        """
        payload, params = _build_snapshot_create(capsule_id, name, overwrite)
        resp = self._http.post(
            "/v1/snapshots", json=payload, params=params, timeout=_LONG_TIMEOUT
        )
        return Template.model_validate(handle_response(resp))

    def list(self, type: str | None = None) -> list[Template]:
        """List snapshot templates.

        Args:
            type (str | None): Filter by template type. Returns all templates
                if not provided.

        Returns:
            list[Template]: Matching snapshot templates.
        """
        resp = self._http.get("/v1/snapshots", params=_snapshot_list_params(type))
        return [Template.model_validate(item) for item in handle_response(resp)]

    def delete(self, name: str) -> None:
        """Delete a snapshot template by name.

        Args:
            name (str): Template name to delete.

        Raises:
            WrennNotFoundError: If no template with the given name exists.
        """
        resp = self._http.delete(f"/v1/snapshots/{name}")
        handle_response(resp)


class AsyncSnapshotsResource:
    """Async snapshot operations."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def create(
        self,
        capsule_id: str,
        name: str | None = None,
        overwrite: bool = False,
    ) -> Template:
        """Create a snapshot template from a running capsule.

        Args:
            capsule_id (str): ID of the capsule to snapshot.
            name (str | None): Name for the snapshot template. Auto-generated
                if not provided.
            overwrite (bool): If ``True``, overwrite an existing template with
                the same name. Defaults to ``False``.

        Returns:
            Template: The created snapshot template.
        """
        payload, params = _build_snapshot_create(capsule_id, name, overwrite)
        resp = await self._http.post(
            "/v1/snapshots", json=payload, params=params, timeout=_LONG_TIMEOUT
        )
        return Template.model_validate(handle_response(resp))

    async def list(self, type: str | None = None) -> list[Template]:
        """List snapshot templates.

        Args:
            type (str | None): Filter by template type. Returns all templates
                if not provided.

        Returns:
            list[Template]: Matching snapshot templates.
        """
        resp = await self._http.get("/v1/snapshots", params=_snapshot_list_params(type))
        return [Template.model_validate(item) for item in handle_response(resp)]

    async def delete(self, name: str) -> None:
        """Delete a snapshot template by name.

        Args:
            name (str): Template name to delete.

        Raises:
            WrennNotFoundError: If no template with the given name exists.
        """
        resp = await self._http.delete(f"/v1/snapshots/{name}")
        handle_response(resp)


class WrennClient:
    """Synchronous client for the Wrenn API.

    Authenticates with an API key.

    Args:
        api_key: API key (``wrn_...``). Falls back to ``WRENN_API_KEY`` env var.
        base_url: Wrenn API base URL. Falls back to ``WRENN_BASE_URL`` env var.
        proxy_domain: Host suffix for capsule proxy URLs
            (``{port}-{capsule_id}.<domain>``). Falls back to
            ``WRENN_PROXY_DOMAIN`` env, then ``wrenn.dev`` when ``base_url``
            is the default ``app.wrenn.dev`` host, else the ``base_url`` host.
        timeout: HTTP timeout. Accepts ``httpx.Timeout``, a float (seconds),
            or ``None`` for the default (30s read/write/pool, 10s connect).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        proxy_domain: str | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url or os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)
        self._proxy_domain = _resolve_proxy_domain(self._base_url, proxy_domain)
        self._http = _RetryingClient(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
            timeout=_resolve_timeout(timeout),
        )

        self.capsules = CapsulesResource(self._http)
        self.snapshots = SnapshotsResource(self._http)

    @property
    def http(self) -> httpx.Client:
        """The underlying httpx.Client (for sub-objects that need direct access)."""
        return self._http

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> WrennClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()


class AsyncWrennClient:
    """Asynchronous client for the Wrenn API.

    Authenticates with an API key.

    Args:
        api_key: API key (``wrn_...``). Falls back to ``WRENN_API_KEY`` env var.
        base_url: Wrenn API base URL. Falls back to ``WRENN_BASE_URL`` env var.
        proxy_domain: Host suffix for capsule proxy URLs
            (``{port}-{capsule_id}.<domain>``). Falls back to
            ``WRENN_PROXY_DOMAIN`` env, then ``wrenn.dev`` when ``base_url``
            is the default ``app.wrenn.dev`` host, else the ``base_url`` host.
        timeout: HTTP timeout. Accepts ``httpx.Timeout``, a float (seconds),
            or ``None`` for the default (30s read/write/pool, 10s connect).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        proxy_domain: str | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url or os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)
        self._proxy_domain = _resolve_proxy_domain(self._base_url, proxy_domain)
        self._http = _RetryingAsyncClient(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
            timeout=_resolve_timeout(timeout),
        )

        self.capsules = AsyncCapsulesResource(self._http)
        self.snapshots = AsyncSnapshotsResource(self._http)

    @property
    def http(self) -> httpx.AsyncClient:
        """The underlying httpx.AsyncClient."""
        return self._http

    async def aclose(self) -> None:
        """Close the underlying async HTTP connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> AsyncWrennClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.aclose()
