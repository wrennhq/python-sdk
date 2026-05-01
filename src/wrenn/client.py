from __future__ import annotations

import os

import httpx

from wrenn._config import DEFAULT_BASE_URL, ENV_API_KEY, ENV_BASE_URL
from wrenn.exceptions import handle_response

from wrenn.models import (
    Template,
)
from wrenn.models import (
    Capsule as CapsuleModel,
)

_LONG_TIMEOUT = httpx.Timeout(60.0)


def _resolve_api_key(api_key: str | None) -> str:
    resolved = api_key or os.environ.get(ENV_API_KEY)
    if not resolved:
        raise ValueError(
            f"No API key provided. Pass api_key= or set the {ENV_API_KEY} environment variable."
        )
    return resolved


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
        payload: dict = {}
        if template is not None:
            payload["template"] = template
        if vcpus is not None:
            payload["vcpus"] = vcpus
        if memory_mb is not None:
            payload["memory_mb"] = memory_mb
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        resp = self._http.post("/v1/capsules", json=payload)
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
        resp = self._http.post(f"/v1/capsules/{id}/pause", timeout=_LONG_TIMEOUT)
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
        payload: dict = {}
        if template is not None:
            payload["template"] = template
        if vcpus is not None:
            payload["vcpus"] = vcpus
        if memory_mb is not None:
            payload["memory_mb"] = memory_mb
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        resp = await self._http.post("/v1/capsules", json=payload)
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
        resp = await self._http.post(f"/v1/capsules/{id}/pause", timeout=_LONG_TIMEOUT)
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
        payload: dict = {"sandbox_id": capsule_id}
        if name is not None:
            payload["name"] = name
        params: dict = {}
        if overwrite:
            params["overwrite"] = "true"
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
        params: dict = {}
        if type is not None:
            params["type"] = type
        resp = self._http.get("/v1/snapshots", params=params)
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
        payload: dict = {"sandbox_id": capsule_id}
        if name is not None:
            payload["name"] = name
        params: dict = {}
        if overwrite:
            params["overwrite"] = "true"
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
        params: dict = {}
        if type is not None:
            params["type"] = type
        resp = await self._http.get("/v1/snapshots", params=params)
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
        base_url: Wrenn API base URL.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url or os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)
        self._http = httpx.Client(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
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
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url or os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
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
