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
    CapsuleStats,
    ChannelResponse,
    CreateChannelRequest,
    CreateHostResponse,
    Host,
    HostDeletePreview,
    MeResponse,
    RotateConfigRequest,
    SignupResponse,
    Template,
    TeamDetail,
    TeamMember,
    TeamWithRole,
    TestChannelRequest,
    UpdateChannelRequest,
    UsageResponse,
    UserSearchResult,
)
from wrenn.models import (
    Capsule as CapsuleModel,
)

DEFAULT_BASE_URL = "https://api.wrenn.dev"

_MGMT_AUTH_MSG = "This operation requires a JWT token. Pass token= to WrennClient."
_DATA_AUTH_MSG = "Capsule operations require an API key. Pass api_key= to WrennClient."


def _require(
    client: httpx.Client | httpx.AsyncClient | None, message: str
) -> httpx.Client | httpx.AsyncClient:
    if client is None:
        raise ValueError(message)
    return client


class AuthResource:
    """Sync auth operations."""

    def __init__(
        self,
        public_http: httpx.Client,
        mgmt_http: httpx.Client | None,
    ) -> None:
        self._public_http = public_http
        self._mgmt_http = mgmt_http

    def signup(self, email: str, password: str, name: str) -> SignupResponse:
        resp = self._public_http.post(
            "/v1/auth/signup",
            json={"email": email, "password": password, "name": name},
        )
        return SignupResponse.model_validate(handle_response(resp))

    def login(self, email: str, password: str) -> AuthResponse:
        resp = self._public_http.post(
            "/v1/auth/login", json={"email": email, "password": password}
        )
        return AuthResponse.model_validate(handle_response(resp))

    def activate(self, token: str) -> AuthResponse:
        resp = self._public_http.post("/v1/auth/activate", json={"token": token})
        return AuthResponse.model_validate(handle_response(resp))

    def switch_team(self, team_id: str) -> AuthResponse:
        http = _require(self._mgmt_http, _MGMT_AUTH_MSG)
        resp = http.post("/v1/auth/switch-team", json={"team_id": team_id})
        return AuthResponse.model_validate(handle_response(resp))


class AsyncAuthResource:
    """Async auth operations."""

    def __init__(
        self,
        public_http: httpx.AsyncClient,
        mgmt_http: httpx.AsyncClient | None,
    ) -> None:
        self._public_http = public_http
        self._mgmt_http = mgmt_http

    async def signup(self, email: str, password: str, name: str) -> SignupResponse:
        resp = await self._public_http.post(
            "/v1/auth/signup",
            json={"email": email, "password": password, "name": name},
        )
        return SignupResponse.model_validate(handle_response(resp))

    async def login(self, email: str, password: str) -> AuthResponse:
        resp = await self._public_http.post(
            "/v1/auth/login", json={"email": email, "password": password}
        )
        return AuthResponse.model_validate(handle_response(resp))

    async def activate(self, token: str) -> AuthResponse:
        resp = await self._public_http.post("/v1/auth/activate", json={"token": token})
        return AuthResponse.model_validate(handle_response(resp))

    async def switch_team(self, team_id: str) -> AuthResponse:
        http = _require(self._mgmt_http, _MGMT_AUTH_MSG)
        resp = await http.post("/v1/auth/switch-team", json={"team_id": team_id})
        return AuthResponse.model_validate(handle_response(resp))


class AccountResource:
    """Sync account operations."""

    def __init__(
        self,
        public_http: httpx.Client,
        mgmt_http: httpx.Client | None,
    ) -> None:
        self._public_http = public_http
        self._mgmt_http = mgmt_http

    def _require_mgmt(self) -> httpx.Client:
        return _require(self._mgmt_http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    def get(self) -> MeResponse:
        resp = self._require_mgmt().get("/v1/me")
        return MeResponse.model_validate(handle_response(resp))

    def update_name(self, name: str) -> AuthResponse:
        resp = self._require_mgmt().patch("/v1/me", json={"name": name})
        return AuthResponse.model_validate(handle_response(resp))

    def delete(self, confirmation: str) -> None:
        resp = self._require_mgmt().delete(
            "/v1/me", json={"confirmation": confirmation}
        )
        handle_response(resp)

    def change_password(
        self,
        new_password: str,
        current_password: str | None = None,
        confirm_password: str | None = None,
    ) -> None:
        payload: dict = {"new_password": new_password}
        if current_password is not None:
            payload["current_password"] = current_password
        if confirm_password is not None:
            payload["confirm_password"] = confirm_password
        resp = self._require_mgmt().post("/v1/me/password", json=payload)
        handle_response(resp)

    def request_password_reset(self, email: str) -> None:
        resp = self._public_http.post("/v1/me/password/reset", json={"email": email})
        handle_response(resp)

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        resp = self._public_http.post(
            "/v1/me/password/reset/confirm",
            json={"token": token, "new_password": new_password},
        )
        handle_response(resp)

    def connect_provider(self, provider: str) -> dict:
        resp = self._require_mgmt().get(f"/v1/me/providers/{provider}/connect")
        return handle_response(resp)

    def disconnect_provider(self, provider: str) -> None:
        resp = self._require_mgmt().delete(f"/v1/me/providers/{provider}")
        handle_response(resp)


class AsyncAccountResource:
    """Async account operations."""

    def __init__(
        self,
        public_http: httpx.AsyncClient,
        mgmt_http: httpx.AsyncClient | None,
    ) -> None:
        self._public_http = public_http
        self._mgmt_http = mgmt_http

    def _require_mgmt(self) -> httpx.AsyncClient:
        return _require(self._mgmt_http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    async def get(self) -> MeResponse:
        resp = await self._require_mgmt().get("/v1/me")
        return MeResponse.model_validate(handle_response(resp))

    async def update_name(self, name: str) -> AuthResponse:
        resp = await self._require_mgmt().patch("/v1/me", json={"name": name})
        return AuthResponse.model_validate(handle_response(resp))

    async def delete(self, confirmation: str) -> None:
        resp = await self._require_mgmt().delete(
            "/v1/me", json={"confirmation": confirmation}
        )
        handle_response(resp)

    async def change_password(
        self,
        new_password: str,
        current_password: str | None = None,
        confirm_password: str | None = None,
    ) -> None:
        payload: dict = {"new_password": new_password}
        if current_password is not None:
            payload["current_password"] = current_password
        if confirm_password is not None:
            payload["confirm_password"] = confirm_password
        resp = await self._require_mgmt().post("/v1/me/password", json=payload)
        handle_response(resp)

    async def request_password_reset(self, email: str) -> None:
        resp = await self._public_http.post(
            "/v1/me/password/reset", json={"email": email}
        )
        handle_response(resp)

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        resp = await self._public_http.post(
            "/v1/me/password/reset/confirm",
            json={"token": token, "new_password": new_password},
        )
        handle_response(resp)

    async def connect_provider(self, provider: str) -> dict:
        resp = await self._require_mgmt().get(f"/v1/me/providers/{provider}/connect")
        return handle_response(resp)

    async def disconnect_provider(self, provider: str) -> None:
        resp = await self._require_mgmt().delete(f"/v1/me/providers/{provider}")
        handle_response(resp)


class APIKeysResource:
    """Sync API key operations."""

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http

    def _require(self) -> httpx.Client:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    def create(self, name: str | None = None) -> APIKeyResponse:
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        resp = self._require().post("/v1/api-keys", json=payload)
        return APIKeyResponse.model_validate(handle_response(resp))

    def list(self) -> list[APIKeyResponse]:
        resp = self._require().get("/v1/api-keys")
        return [APIKeyResponse.model_validate(item) for item in handle_response(resp)]

    def delete(self, id: str) -> None:
        resp = self._require().delete(f"/v1/api-keys/{id}")
        handle_response(resp)


class AsyncAPIKeysResource:
    """Async API key operations."""

    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    async def create(self, name: str | None = None) -> APIKeyResponse:
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        resp = await self._require().post("/v1/api-keys", json=payload)
        return APIKeyResponse.model_validate(handle_response(resp))

    async def list(self) -> list[APIKeyResponse]:
        resp = await self._require().get("/v1/api-keys")
        return [APIKeyResponse.model_validate(item) for item in handle_response(resp)]

    async def delete(self, id: str) -> None:
        resp = await self._require().delete(f"/v1/api-keys/{id}")
        handle_response(resp)


class UsersResource:
    """Sync user operations."""

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http

    def _require(self) -> httpx.Client:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    def search(self, email: str) -> list[UserSearchResult]:
        resp = self._require().get("/v1/users/search", params={"email": email})
        return [UserSearchResult.model_validate(item) for item in handle_response(resp)]


class AsyncUsersResource:
    """Async user operations."""

    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    async def search(self, email: str) -> list[UserSearchResult]:
        resp = await self._require().get("/v1/users/search", params={"email": email})
        return [UserSearchResult.model_validate(item) for item in handle_response(resp)]


class TeamsResource:
    """Sync team operations."""

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http

    def _require(self) -> httpx.Client:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    def list(self) -> list[TeamWithRole]:
        resp = self._require().get("/v1/teams")
        return [TeamWithRole.model_validate(item) for item in handle_response(resp)]

    def create(self, name: str) -> TeamWithRole:
        resp = self._require().post("/v1/teams", json={"name": name})
        return TeamWithRole.model_validate(handle_response(resp))

    def get(self, id: str) -> TeamDetail:
        resp = self._require().get(f"/v1/teams/{id}")
        return TeamDetail.model_validate(handle_response(resp))

    def rename(self, id: str, name: str) -> None:
        resp = self._require().patch(f"/v1/teams/{id}", json={"name": name})
        handle_response(resp)

    def delete(self, id: str) -> None:
        resp = self._require().delete(f"/v1/teams/{id}")
        handle_response(resp)

    def list_members(self, id: str) -> list[TeamMember]:
        resp = self._require().get(f"/v1/teams/{id}/members")
        return [TeamMember.model_validate(item) for item in handle_response(resp)]

    def add_member(self, id: str, email: str) -> TeamMember:
        resp = self._require().post(f"/v1/teams/{id}/members", json={"email": email})
        return TeamMember.model_validate(handle_response(resp))

    def update_member_role(self, id: str, uid: str, role: str) -> None:
        resp = self._require().patch(
            f"/v1/teams/{id}/members/{uid}", json={"role": role}
        )
        handle_response(resp)

    def remove_member(self, id: str, uid: str) -> None:
        resp = self._require().delete(f"/v1/teams/{id}/members/{uid}")
        handle_response(resp)

    def leave(self, id: str) -> None:
        resp = self._require().post(f"/v1/teams/{id}/leave")
        handle_response(resp)


class AsyncTeamsResource:
    """Async team operations."""

    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    async def list(self) -> list[TeamWithRole]:
        resp = await self._require().get("/v1/teams")
        return [TeamWithRole.model_validate(item) for item in handle_response(resp)]

    async def create(self, name: str) -> TeamWithRole:
        resp = await self._require().post("/v1/teams", json={"name": name})
        return TeamWithRole.model_validate(handle_response(resp))

    async def get(self, id: str) -> TeamDetail:
        resp = await self._require().get(f"/v1/teams/{id}")
        return TeamDetail.model_validate(handle_response(resp))

    async def rename(self, id: str, name: str) -> None:
        resp = await self._require().patch(f"/v1/teams/{id}", json={"name": name})
        handle_response(resp)

    async def delete(self, id: str) -> None:
        resp = await self._require().delete(f"/v1/teams/{id}")
        handle_response(resp)

    async def list_members(self, id: str) -> list[TeamMember]:
        resp = await self._require().get(f"/v1/teams/{id}/members")
        return [TeamMember.model_validate(item) for item in handle_response(resp)]

    async def add_member(self, id: str, email: str) -> TeamMember:
        resp = await self._require().post(
            f"/v1/teams/{id}/members", json={"email": email}
        )
        return TeamMember.model_validate(handle_response(resp))

    async def update_member_role(self, id: str, uid: str, role: str) -> None:
        resp = await self._require().patch(
            f"/v1/teams/{id}/members/{uid}", json={"role": role}
        )
        handle_response(resp)

    async def remove_member(self, id: str, uid: str) -> None:
        resp = await self._require().delete(f"/v1/teams/{id}/members/{uid}")
        handle_response(resp)

    async def leave(self, id: str) -> None:
        resp = await self._require().post(f"/v1/teams/{id}/leave")
        handle_response(resp)


class CapsulesResource:
    """Sync capsule control-plane operations."""

    def __init__(
        self,
        http: httpx.Client | None,
        base_url: str,
        api_key: str | None = None,
        token: str | None = None,
    ) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key
        self._token = token

    def _require(self) -> httpx.Client:
        return _require(self._http, _DATA_AUTH_MSG)  # type: ignore[return-value]

    def create(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout_sec: int | None = None,
    ) -> Capsule:
        http = self._require()
        payload: dict = {}
        if template is not None:
            payload["template"] = template
        if vcpus is not None:
            payload["vcpus"] = vcpus
        if memory_mb is not None:
            payload["memory_mb"] = memory_mb
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        resp = http.post("/v1/capsules", json=payload)
        model = CapsuleModel.model_validate(handle_response(resp))
        cap = Capsule.model_validate(model.model_dump())
        cap._bind(http, self._base_url, self._api_key, self._token)
        return cap

    def list(self) -> list[CapsuleModel]:
        resp = self._require().get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    def get(self, id: str) -> CapsuleModel:
        resp = self._require().get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    def destroy(self, id: str) -> None:
        resp = self._require().delete(f"/v1/capsules/{id}")
        handle_response(resp)

    def stats(self, range: str | None = None) -> CapsuleStats:
        params: dict = {}
        if range is not None:
            params["range"] = range
        resp = self._require().get("/v1/capsules/stats", params=params)
        return CapsuleStats.model_validate(handle_response(resp))

    def usage(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> UsageResponse:
        params: dict = {}
        if from_date is not None:
            params["from"] = from_date
        if to_date is not None:
            params["to"] = to_date
        resp = self._require().get("/v1/capsules/usage", params=params)
        return UsageResponse.model_validate(handle_response(resp))


class AsyncCapsulesResource:
    """Async capsule control-plane operations."""

    def __init__(
        self,
        http: httpx.AsyncClient | None,
        base_url: str,
        api_key: str | None = None,
        token: str | None = None,
    ) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key
        self._token = token

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _DATA_AUTH_MSG)  # type: ignore[return-value]

    async def create(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout_sec: int | None = None,
    ) -> Capsule:
        http = self._require()
        payload: dict = {}
        if template is not None:
            payload["template"] = template
        if vcpus is not None:
            payload["vcpus"] = vcpus
        if memory_mb is not None:
            payload["memory_mb"] = memory_mb
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        resp = await http.post("/v1/capsules", json=payload)
        model = CapsuleModel.model_validate(handle_response(resp))
        cap = Capsule.model_validate(model.model_dump())
        cap._bind(http, self._base_url, self._api_key, self._token)
        return cap

    async def list(self) -> list[CapsuleModel]:
        resp = await self._require().get("/v1/capsules")
        return [CapsuleModel.model_validate(item) for item in handle_response(resp)]

    async def get(self, id: str) -> CapsuleModel:
        resp = await self._require().get(f"/v1/capsules/{id}")
        return CapsuleModel.model_validate(handle_response(resp))

    async def destroy(self, id: str) -> None:
        resp = await self._require().delete(f"/v1/capsules/{id}")
        handle_response(resp)

    async def stats(self, range: str | None = None) -> CapsuleStats:
        params: dict = {}
        if range is not None:
            params["range"] = range
        resp = await self._require().get("/v1/capsules/stats", params=params)
        return CapsuleStats.model_validate(handle_response(resp))

    async def usage(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> UsageResponse:
        params: dict = {}
        if from_date is not None:
            params["from"] = from_date
        if to_date is not None:
            params["to"] = to_date
        resp = await self._require().get("/v1/capsules/usage", params=params)
        return UsageResponse.model_validate(handle_response(resp))


class SnapshotsResource:
    """Sync snapshot operations."""

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http

    def _require(self) -> httpx.Client:
        return _require(self._http, _DATA_AUTH_MSG)  # type: ignore[return-value]

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
        resp = self._require().post("/v1/snapshots", json=payload, params=params)
        return Template.model_validate(handle_response(resp))

    def list(self, type: str | None = None) -> list[Template]:
        params: dict = {}
        if type is not None:
            params["type"] = type
        resp = self._require().get("/v1/snapshots", params=params)
        return [Template.model_validate(item) for item in handle_response(resp)]

    def delete(self, name: str) -> None:
        resp = self._require().delete(f"/v1/snapshots/{name}")
        handle_response(resp)


class AsyncSnapshotsResource:
    """Async snapshot operations."""

    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _DATA_AUTH_MSG)  # type: ignore[return-value]

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
        resp = await self._require().post("/v1/snapshots", json=payload, params=params)
        return Template.model_validate(handle_response(resp))

    async def list(self, type: str | None = None) -> list[Template]:
        params: dict = {}
        if type is not None:
            params["type"] = type
        resp = await self._require().get("/v1/snapshots", params=params)
        return [Template.model_validate(item) for item in handle_response(resp)]

    async def delete(self, name: str) -> None:
        resp = await self._require().delete(f"/v1/snapshots/{name}")
        handle_response(resp)


class HostsResource:
    """Sync host operations."""

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http

    def _require(self) -> httpx.Client:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

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
        resp = self._require().post("/v1/hosts", json=payload)
        return CreateHostResponse.model_validate(handle_response(resp))

    def list(self) -> list[Host]:
        resp = self._require().get("/v1/hosts")
        return [Host.model_validate(item) for item in handle_response(resp)]

    def get(self, id: str) -> Host:
        resp = self._require().get(f"/v1/hosts/{id}")
        return Host.model_validate(handle_response(resp))

    def delete(self, id: str, force: bool = False) -> None:
        params: dict = {}
        if force:
            params["force"] = "true"
        resp = self._require().delete(f"/v1/hosts/{id}", params=params)
        handle_response(resp)

    def regenerate_token(self, id: str) -> CreateHostResponse:
        resp = self._require().post(f"/v1/hosts/{id}/token")
        return CreateHostResponse.model_validate(handle_response(resp))

    def delete_preview(self, id: str) -> HostDeletePreview:
        resp = self._require().get(f"/v1/hosts/{id}/delete-preview")
        return HostDeletePreview.model_validate(handle_response(resp))

    def list_tags(self, id: str) -> builtins.list[str]:
        resp = self._require().get(f"/v1/hosts/{id}/tags")
        return cast(builtins.list[str], handle_response(resp))

    def add_tag(self, id: str, tag: str) -> None:
        resp = self._require().post(f"/v1/hosts/{id}/tags", json={"tag": tag})
        handle_response(resp)

    def remove_tag(self, id: str, tag: str) -> None:
        resp = self._require().delete(f"/v1/hosts/{id}/tags/{tag}")
        handle_response(resp)


class AsyncHostsResource:
    """Async host operations."""

    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

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
        resp = await self._require().post("/v1/hosts", json=payload)
        return CreateHostResponse.model_validate(handle_response(resp))

    async def list(self) -> list[Host]:
        resp = await self._require().get("/v1/hosts")
        return [Host.model_validate(item) for item in handle_response(resp)]

    async def get(self, id: str) -> Host:
        resp = await self._require().get(f"/v1/hosts/{id}")
        return Host.model_validate(handle_response(resp))

    async def delete(self, id: str, force: bool = False) -> None:
        params: dict = {}
        if force:
            params["force"] = "true"
        resp = await self._require().delete(f"/v1/hosts/{id}", params=params)
        handle_response(resp)

    async def regenerate_token(self, id: str) -> CreateHostResponse:
        resp = await self._require().post(f"/v1/hosts/{id}/token")
        return CreateHostResponse.model_validate(handle_response(resp))

    async def delete_preview(self, id: str) -> HostDeletePreview:
        resp = await self._require().get(f"/v1/hosts/{id}/delete-preview")
        return HostDeletePreview.model_validate(handle_response(resp))

    async def list_tags(self, id: str) -> builtins.list[str]:
        resp = await self._require().get(f"/v1/hosts/{id}/tags")
        return cast(builtins.list[str], handle_response(resp))

    async def add_tag(self, id: str, tag: str) -> None:
        resp = await self._require().post(f"/v1/hosts/{id}/tags", json={"tag": tag})
        handle_response(resp)

    async def remove_tag(self, id: str, tag: str) -> None:
        resp = await self._require().delete(f"/v1/hosts/{id}/tags/{tag}")
        handle_response(resp)


class ChannelsResource:
    """Sync notification channel operations."""

    def __init__(self, http: httpx.Client | None) -> None:
        self._http = http

    def _require(self) -> httpx.Client:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    def create(self, request: CreateChannelRequest) -> ChannelResponse:
        resp = self._require().post(
            "/v1/channels", json=request.model_dump(mode="json", exclude_none=True)
        )
        return ChannelResponse.model_validate(handle_response(resp))

    def list(self) -> list[ChannelResponse]:
        resp = self._require().get("/v1/channels")
        return [ChannelResponse.model_validate(item) for item in handle_response(resp)]

    def test(self, request: TestChannelRequest) -> dict:
        resp = self._require().post(
            "/v1/channels/test", json=request.model_dump(mode="json", exclude_none=True)
        )
        return handle_response(resp)

    def get(self, id: str) -> ChannelResponse:
        resp = self._require().get(f"/v1/channels/{id}")
        return ChannelResponse.model_validate(handle_response(resp))

    def update(self, id: str, request: UpdateChannelRequest) -> ChannelResponse:
        resp = self._require().patch(
            f"/v1/channels/{id}",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return ChannelResponse.model_validate(handle_response(resp))

    def delete(self, id: str) -> None:
        resp = self._require().delete(f"/v1/channels/{id}")
        handle_response(resp)

    def rotate_config(self, id: str, request: RotateConfigRequest) -> ChannelResponse:
        resp = self._require().put(
            f"/v1/channels/{id}/config",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return ChannelResponse.model_validate(handle_response(resp))


class AsyncChannelsResource:
    """Async notification channel operations."""

    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    def _require(self) -> httpx.AsyncClient:
        return _require(self._http, _MGMT_AUTH_MSG)  # type: ignore[return-value]

    async def create(self, request: CreateChannelRequest) -> ChannelResponse:
        resp = await self._require().post(
            "/v1/channels", json=request.model_dump(mode="json", exclude_none=True)
        )
        return ChannelResponse.model_validate(handle_response(resp))

    async def list(self) -> list[ChannelResponse]:
        resp = await self._require().get("/v1/channels")
        return [ChannelResponse.model_validate(item) for item in handle_response(resp)]

    async def test(self, request: TestChannelRequest) -> dict:
        resp = await self._require().post(
            "/v1/channels/test", json=request.model_dump(mode="json", exclude_none=True)
        )
        return handle_response(resp)

    async def get(self, id: str) -> ChannelResponse:
        resp = await self._require().get(f"/v1/channels/{id}")
        return ChannelResponse.model_validate(handle_response(resp))

    async def update(self, id: str, request: UpdateChannelRequest) -> ChannelResponse:
        resp = await self._require().patch(
            f"/v1/channels/{id}",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return ChannelResponse.model_validate(handle_response(resp))

    async def delete(self, id: str) -> None:
        resp = await self._require().delete(f"/v1/channels/{id}")
        handle_response(resp)

    async def rotate_config(
        self, id: str, request: RotateConfigRequest
    ) -> ChannelResponse:
        resp = await self._require().put(
            f"/v1/channels/{id}/config",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return ChannelResponse.model_validate(handle_response(resp))


def _make_client(base_url: str, headers: dict[str, str]) -> httpx.Client:
    return httpx.Client(base_url=base_url, headers=headers)


def _make_async_client(base_url: str, headers: dict[str, str]) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, headers=headers)


class WrennClient:
    """Synchronous client for the Wrenn API.

    Authenticate with an API key, a JWT token, or both.

    - ``api_key``: for capsule and snapshot operations (sent as ``X-API-Key``).
    - ``token``: for management operations like account, teams, hosts
      (sent as ``Authorization: Bearer``).

    Args:
        api_key: API key (``wrn_...``).
        token: JWT token.
        base_url: Wrenn Control Plane URL.
    """

    def __init__(
        self,
        api_key: str | None = None,
        token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._token = token
        self._base_url = base_url

        self._public_http = _make_client(base_url, {})
        self._mgmt_http: httpx.Client | None = None
        if token:
            self._mgmt_http = _make_client(
                base_url, {"Authorization": f"Bearer {token}"}
            )
        self._data_http: httpx.Client | None = None
        if api_key:
            self._data_http = _make_client(base_url, {"X-API-Key": api_key})

        self.auth = AuthResource(self._public_http, self._mgmt_http)
        self.account = AccountResource(self._public_http, self._mgmt_http)
        self.api_keys = APIKeysResource(self._mgmt_http)
        self.users = UsersResource(self._mgmt_http)
        self.teams = TeamsResource(self._mgmt_http)
        self.capsules = CapsulesResource(self._data_http, base_url, api_key, token)
        self.snapshots = SnapshotsResource(self._data_http)
        self.hosts = HostsResource(self._mgmt_http)
        self.channels = ChannelsResource(self._mgmt_http)

    @property
    def sandboxes(self) -> CapsulesResource:
        warnings.warn(
            "'client.sandboxes' is deprecated, use 'client.capsules' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.capsules

    def close(self) -> None:
        """Close the underlying HTTP connection pool(s)."""
        self._public_http.close()
        if self._mgmt_http is not None:
            self._mgmt_http.close()
        if self._data_http is not None:
            self._data_http.close()

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

    Authenticate with an API key, a JWT token, or both.

    - ``api_key``: for capsule and snapshot operations (sent as ``X-API-Key``).
    - ``token``: for management operations like account, teams, hosts
      (sent as ``Authorization: Bearer``).

    Args:
        api_key: API key (``wrn_...``).
        token: JWT token.
        base_url: Wrenn Control Plane URL.
    """

    def __init__(
        self,
        api_key: str | None = None,
        token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._token = token
        self._base_url = base_url

        self._public_http = _make_async_client(base_url, {})
        self._mgmt_http: httpx.AsyncClient | None = None
        if token:
            self._mgmt_http = _make_async_client(
                base_url, {"Authorization": f"Bearer {token}"}
            )
        self._data_http: httpx.AsyncClient | None = None
        if api_key:
            self._data_http = _make_async_client(base_url, {"X-API-Key": api_key})

        self.auth = AsyncAuthResource(self._public_http, self._mgmt_http)
        self.account = AsyncAccountResource(self._public_http, self._mgmt_http)
        self.api_keys = AsyncAPIKeysResource(self._mgmt_http)
        self.users = AsyncUsersResource(self._mgmt_http)
        self.teams = AsyncTeamsResource(self._mgmt_http)
        self.capsules = AsyncCapsulesResource(self._data_http, base_url, api_key, token)
        self.snapshots = AsyncSnapshotsResource(self._data_http)
        self.hosts = AsyncHostsResource(self._mgmt_http)
        self.channels = AsyncChannelsResource(self._mgmt_http)

    @property
    def sandboxes(self) -> AsyncCapsulesResource:
        warnings.warn(
            "'client.sandboxes' is deprecated, use 'client.capsules' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.capsules

    async def aclose(self) -> None:
        """Close the underlying async HTTP connection pool(s)."""
        await self._public_http.aclose()
        if self._mgmt_http is not None:
            await self._mgmt_http.aclose()
        if self._data_http is not None:
            await self._data_http.aclose()

    async def __aenter__(self) -> AsyncWrennClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.aclose()
