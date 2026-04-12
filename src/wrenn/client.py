from __future__ import annotations

import builtins
import warnings
from typing import cast

import httpx

from wrenn.capsule import Capsule
from wrenn.exceptions import handle_response
from wrenn.models import (
    APIKeyResponse,
    AuthResponse,
    CreateHostResponse,
    Host,
    Template,
)
from wrenn.models import (
    Capsule as CapsuleModel,
)

DEFAULT_BASE_URL = "https://api.wrenn.dev"


def _build_headers(api_key: str | None, token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class AuthResource:
    """Sync auth operations."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def signup(self, email: str, password: str) -> AuthResponse:
        resp = self._http.post(
            "/v1/auth/signup", json={"email": email, "password": password}
        )
        return AuthResponse.model_validate(handle_response(resp))

    def login(self, email: str, password: str) -> AuthResponse:
        resp = self._http.post(
            "/v1/auth/login", json={"email": email, "password": password}
        )
        return AuthResponse.model_validate(handle_response(resp))


class AsyncAuthResource:
    """Async auth operations."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def signup(self, email: str, password: str) -> AuthResponse:
        resp = await self._http.post(
            "/v1/auth/signup", json={"email": email, "password": password}
        )
        return AuthResponse.model_validate(handle_response(resp))

    async def login(self, email: str, password: str) -> AuthResponse:
        resp = await self._http.post(
            "/v1/auth/login", json={"email": email, "password": password}
        )
        return AuthResponse.model_validate(handle_response(resp))


class APIKeysResource:
    """Sync API key operations."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create(self, name: str | None = None) -> APIKeyResponse:
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        resp = self._http.post("/v1/api-keys", json=payload)
        return APIKeyResponse.model_validate(handle_response(resp))

    def list(self) -> list[APIKeyResponse]:
        resp = self._http.get("/v1/api-keys")
        return [APIKeyResponse.model_validate(item) for item in handle_response(resp)]

    def delete(self, id: str) -> None:
        resp = self._http.delete(f"/v1/api-keys/{id}")
        handle_response(resp)


class AsyncAPIKeysResource:
    """Async API key operations."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def create(self, name: str | None = None) -> APIKeyResponse:
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        resp = await self._http.post("/v1/api-keys", json=payload)
        return APIKeyResponse.model_validate(handle_response(resp))

    async def list(self) -> list[APIKeyResponse]:
        resp = await self._http.get("/v1/api-keys")
        return [APIKeyResponse.model_validate(item) for item in handle_response(resp)]

    async def delete(self, id: str) -> None:
        resp = await self._http.delete(f"/v1/api-keys/{id}")
        handle_response(resp)


class CapsulesResource:
    """Sync capsule control-plane operations."""

    def __init__(
        self,
        http: httpx.Client,
        base_url: str,
        api_key: str | None = None,
        token: str | None = None,
    ) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key
        self._token = token

    def create(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout_sec: int | None = None,
    ) -> Capsule:
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
        model = CapsuleModel.model_validate(handle_response(resp))
        cap = Capsule.model_validate(model.model_dump())
        cap._bind(self._http, self._base_url, self._api_key, self._token)
        return cap

    def list(self) -> list[CapsuleModel]:
        resp = self._http.get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    def get(self, id: str) -> CapsuleModel:
        resp = self._http.get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    def destroy(self, id: str) -> None:
        resp = self._http.delete(f"/v1/capsules/{id}")
        handle_response(resp)


class AsyncCapsulesResource:
    """Async capsule control-plane operations."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        api_key: str | None = None,
        token: str | None = None,
    ) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key
        self._token = token

    async def create(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout_sec: int | None = None,
    ) -> Capsule:
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
        model = CapsuleModel.model_validate(handle_response(resp))
        cap = Capsule.model_validate(model.model_dump())
        cap._bind(self._http, self._base_url, self._api_key, self._token)
        return cap

    async def list(self) -> list[CapsuleModel]:
        resp = await self._http.get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    async def get(self, id: str) -> CapsuleModel:
        resp = await self._http.get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    async def destroy(self, id: str) -> None:
        resp = await self._http.delete(f"/v1/capsules/{id}")
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


class HostsResource:
    """Sync host operations."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create(
        self,
        type: str,
        team_id: str | None = None,
        provider: str | None = None,
        availability_zone: str | None = None,
    ) -> CreateHostResponse:
        payload: dict = {"type": type}
        if team_id is not None:
            payload["team_id"] = team_id
        if provider is not None:
            payload["provider"] = provider
        if availability_zone is not None:
            payload["availability_zone"] = availability_zone
        resp = self._http.post("/v1/hosts", json=payload)
        return CreateHostResponse.model_validate(handle_response(resp))

    def list(self) -> list[Host]:
        resp = self._http.get("/v1/hosts")
        return [Host.model_validate(item) for item in handle_response(resp)]

    def get(self, id: str) -> Host:
        resp = self._http.get(f"/v1/hosts/{id}")
        return Host.model_validate(handle_response(resp))

    def delete(self, id: str) -> None:
        resp = self._http.delete(f"/v1/hosts/{id}")
        handle_response(resp)

    def regenerate_token(self, id: str) -> CreateHostResponse:
        resp = self._http.post(f"/v1/hosts/{id}/token")
        return CreateHostResponse.model_validate(handle_response(resp))

    def list_tags(self, id: str) -> builtins.list[str]:
        resp = self._http.get(f"/v1/hosts/{id}/tags")
        return cast(builtins.list[str], handle_response(resp))

    def add_tag(self, id: str, tag: str) -> None:
        resp = self._http.post(f"/v1/hosts/{id}/tags", json={"tag": tag})
        handle_response(resp)

    def remove_tag(self, id: str, tag: str) -> None:
        resp = self._http.delete(f"/v1/hosts/{id}/tags/{tag}")
        handle_response(resp)


class AsyncHostsResource:
    """Async host operations."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def create(
        self,
        type: str,
        team_id: str | None = None,
        provider: str | None = None,
        availability_zone: str | None = None,
    ) -> CreateHostResponse:
        payload: dict = {"type": type}
        if team_id is not None:
            payload["team_id"] = team_id
        if provider is not None:
            payload["provider"] = provider
        if availability_zone is not None:
            payload["availability_zone"] = availability_zone
        resp = await self._http.post("/v1/hosts", json=payload)
        return CreateHostResponse.model_validate(handle_response(resp))

    async def list(self) -> list[Host]:
        resp = await self._http.get("/v1/hosts")
        return [Host.model_validate(item) for item in handle_response(resp)]

    async def get(self, id: str) -> Host:
        resp = await self._http.get(f"/v1/hosts/{id}")
        return Host.model_validate(handle_response(resp))

    async def delete(self, id: str) -> None:
        resp = await self._http.delete(f"/v1/hosts/{id}")
        handle_response(resp)

    async def regenerate_token(self, id: str) -> CreateHostResponse:
        resp = await self._http.post(f"/v1/hosts/{id}/token")
        return CreateHostResponse.model_validate(handle_response(resp))

    async def list_tags(self, id: str) -> builtins.list[str]:
        resp = await self._http.get(f"/v1/hosts/{id}/tags")
        return cast(builtins.list[str], handle_response(resp))

    async def add_tag(self, id: str, tag: str) -> None:
        resp = await self._http.post(f"/v1/hosts/{id}/tags", json={"tag": tag})
        handle_response(resp)

    async def remove_tag(self, id: str, tag: str) -> None:
        resp = await self._http.delete(f"/v1/hosts/{id}/tags/{tag}")
        handle_response(resp)


class WrennClient:
    """Synchronous client for the Wrenn API.

    Authenticate with either an API key or a JWT token.

    Args:
        api_key: API key (``wrn_...``). Sent as ``X-API-Key`` header.
        token: JWT token. Sent as ``Authorization: Bearer`` header.
        base_url: Wrenn Control Plane URL.
    """

    def __init__(
        self,
        api_key: str | None = None,
        token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        if not api_key and not token:
            raise ValueError("Either api_key or token must be provided")

        headers = _build_headers(api_key, token)
        self._http = httpx.Client(base_url=base_url, headers=headers)
        self._api_key = api_key
        self._token = token
        self._base_url = base_url

        self.auth = AuthResource(self._http)
        self.api_keys = APIKeysResource(self._http)
        self.capsules = CapsulesResource(self._http, base_url, api_key, token)
        self.snapshots = SnapshotsResource(self._http)
        self.hosts = HostsResource(self._http)

    @property
    def sandboxes(self) -> CapsulesResource:
        warnings.warn(
            "'client.sandboxes' is deprecated, use 'client.capsules' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.capsules

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

    Authenticate with either an API key or a JWT token.

    Args:
        api_key: API key (``wrn_...``). Sent as ``X-API-Key`` header.
        token: JWT token. Sent as ``Authorization: Bearer`` header.
        base_url: Wrenn Control Plane URL.
    """

    def __init__(
        self,
        api_key: str | None = None,
        token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        if not api_key and not token:
            raise ValueError("Either api_key or token must be provided")

        headers = _build_headers(api_key, token)
        self._http = httpx.AsyncClient(base_url=base_url, headers=headers)
        self._api_key = api_key
        self._token = token
        self._base_url = base_url

        self.auth = AsyncAuthResource(self._http)
        self.api_keys = AsyncAPIKeysResource(self._http)
        self.capsules = AsyncCapsulesResource(self._http, base_url, api_key, token)
        self.snapshots = AsyncSnapshotsResource(self._http)
        self.hosts = AsyncHostsResource(self._http)

    @property
    def sandboxes(self) -> AsyncCapsulesResource:
        warnings.warn(
            "'client.sandboxes' is deprecated, use 'client.capsules' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.capsules

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
