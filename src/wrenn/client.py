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
        resp = self._http.get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    def get(self, id: str) -> CapsuleModel:
        resp = self._http.get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    def destroy(self, id: str) -> None:
        resp = self._http.delete(f"/v1/capsules/{id}")
        handle_response(resp)

    def pause(self, id: str) -> CapsuleModel:
        resp = self._http.post(f"/v1/capsules/{id}/pause")
        return CapsuleModel.model_validate(handle_response(resp))

    def resume(self, id: str) -> CapsuleModel:
        resp = self._http.post(f"/v1/capsules/{id}/resume")
        return CapsuleModel.model_validate(handle_response(resp))

    def ping(self, id: str) -> None:
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
        resp = await self._http.get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    async def get(self, id: str) -> CapsuleModel:
        resp = await self._http.get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    async def destroy(self, id: str) -> None:
        resp = await self._http.delete(f"/v1/capsules/{id}")
        handle_response(resp)

    async def pause(self, id: str) -> CapsuleModel:
        resp = await self._http.post(f"/v1/capsules/{id}/pause")
        return CapsuleModel.model_validate(handle_response(resp))

    async def resume(self, id: str) -> CapsuleModel:
        resp = await self._http.post(f"/v1/capsules/{id}/resume")
        return CapsuleModel.model_validate(handle_response(resp))

    async def ping(self, id: str) -> None:
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
        payload: dict = {"sandbox_id": capsule_id}
        if name is not None:
            payload["name"] = name
        params: dict = {}
        if overwrite:
            params["overwrite"] = "true"
        resp = self._http.post("/v1/snapshots", json=payload, params=params)
        return Template.model_validate(handle_response(resp))

    def list(self, type: str | None = None) -> list[Template]:
        params: dict = {}
        if type is not None:
            params["type"] = type
        resp = self._http.get("/v1/snapshots", params=params)
        return [Template.model_validate(item) for item in handle_response(resp)]

    def delete(self, name: str) -> None:
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
        payload: dict = {"sandbox_id": capsule_id}
        if name is not None:
            payload["name"] = name
        params: dict = {}
        if overwrite:
            params["overwrite"] = "true"
        resp = await self._http.post("/v1/snapshots", json=payload, params=params)
        return Template.model_validate(handle_response(resp))

    async def list(self, type: str | None = None) -> list[Template]:
        params: dict = {}
        if type is not None:
            params["type"] = type
        resp = await self._http.get("/v1/snapshots", params=params)
        return [Template.model_validate(item) for item in handle_response(resp)]

    async def delete(self, name: str) -> None:
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
