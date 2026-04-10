from __future__ import annotations

import pytest
import respx

from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.exceptions import (
    WrennAgentError,
    WrennAuthenticationError,
    WrennConflictError,
    WrennForbiddenError,
    WrennHostHasSandboxesError,
    WrennInternalError,
    WrennNotFoundError,
    WrennValidationError,
)
from wrenn.models import (
    APIKeyResponse,
    AuthResponse,
    CreateHostResponse,
    Host,
    Sandbox,
    Status,
    Template,
)


@pytest.fixture
def client():
    with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
        yield c


@pytest.fixture
def async_client():
    return AsyncWrennClient(api_key="wrn_test1234567890abcdef12345678")


class TestAuth:
    @respx.mock
    def test_signup(self, client):
        respx.post("https://api.wrenn.dev/v1/auth/signup").respond(
            201,
            json={
                "token": "jwt-token",
                "user_id": "u-1",
                "team_id": "t-1",
                "email": "a@b.com",
            },
        )
        resp = client.auth.signup("a@b.com", "password123")
        assert isinstance(resp, AuthResponse)
        assert resp.token == "jwt-token"
        assert resp.user_id == "u-1"

    @respx.mock
    def test_login(self, client):
        respx.post("https://api.wrenn.dev/v1/auth/login").respond(
            200,
            json={"token": "jwt-token", "email": "a@b.com"},
        )
        resp = client.auth.login("a@b.com", "password123")
        assert resp.token == "jwt-token"


class TestAPIKeys:
    @respx.mock
    def test_create(self, client):
        respx.post("https://api.wrenn.dev/v1/api-keys").respond(
            201,
            json={
                "id": "key-1",
                "name": "my-key",
                "key_prefix": "wrn_ab12cd34",
                "key": "wrn_ab12cd34fullkey",
            },
        )
        resp = client.api_keys.create(name="my-key")
        assert isinstance(resp, APIKeyResponse)
        assert resp.name == "my-key"
        assert resp.key == "wrn_ab12cd34fullkey"

    @respx.mock
    def test_list(self, client):
        respx.get("https://api.wrenn.dev/v1/api-keys").respond(
            200,
            json=[{"id": "key-1", "name": "k1"}, {"id": "key-2", "name": "k2"}],
        )
        keys = client.api_keys.list()
        assert len(keys) == 2
        assert keys[0].id == "key-1"

    @respx.mock
    def test_delete(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/api-keys/key-1").respond(204)
        client.api_keys.delete("key-1")
        assert route.called


class TestSandboxes:
    @respx.mock
    def test_create(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201,
            json={
                "id": "sb-1",
                "status": "pending",
                "template": "base-python",
                "vcpus": 2,
                "memory_mb": 1024,
            },
        )
        resp = client.sandboxes.create(template="base-python", vcpus=2, memory_mb=1024)
        assert isinstance(resp, Sandbox)
        assert resp.id == "sb-1"
        assert resp.status == Status.pending

    @respx.mock
    def test_create_defaults(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201, json={"id": "sb-2", "status": "pending"}
        )
        resp = client.sandboxes.create()
        assert resp.id == "sb-2"

    @respx.mock
    def test_list(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes").respond(
            200, json=[{"id": "sb-1", "status": "running"}]
        )
        boxes = client.sandboxes.list()
        assert len(boxes) == 1
        assert boxes[0].status == Status.running

    @respx.mock
    def test_get(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes/sb-1").respond(
            200, json={"id": "sb-1", "status": "running"}
        )
        resp = client.sandboxes.get("sb-1")
        assert resp.id == "sb-1"

    @respx.mock
    def test_destroy(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/sandboxes/sb-1").respond(204)
        client.sandboxes.destroy("sb-1")
        assert route.called


class TestSnapshots:
    @respx.mock
    def test_create(self, client):
        respx.post("https://api.wrenn.dev/v1/snapshots").respond(
            201,
            json={"name": "snap-1", "type": "snapshot", "vcpus": 1},
        )
        resp = client.snapshots.create(sandbox_id="sb-1", name="snap-1")
        assert isinstance(resp, Template)
        assert resp.name == "snap-1"

    @respx.mock
    def test_create_with_overwrite(self, client):
        route = respx.post("https://api.wrenn.dev/v1/snapshots").respond(
            201, json={"name": "snap-1", "type": "snapshot"}
        )
        client.snapshots.create(sandbox_id="sb-1", overwrite=True)
        req = route.calls[0].request
        assert "overwrite=true" in str(req.url)

    @respx.mock
    def test_list(self, client):
        respx.get("https://api.wrenn.dev/v1/snapshots").respond(
            200, json=[{"name": "base-python", "type": "base"}]
        )
        snaps = client.snapshots.list()
        assert len(snaps) == 1

    @respx.mock
    def test_list_with_filter(self, client):
        route = respx.get("https://api.wrenn.dev/v1/snapshots").respond(200, json=[])
        client.snapshots.list(type="snapshot")
        req = route.calls[0].request
        assert "type=snapshot" in str(req.url)

    @respx.mock
    def test_delete(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/snapshots/snap-1").respond(204)
        client.snapshots.delete("snap-1")
        assert route.called


class TestHosts:
    @respx.mock
    def test_create(self, client):
        respx.post("https://api.wrenn.dev/v1/hosts").respond(
            201,
            json={
                "host": {"id": "h-1", "type": "regular", "status": "pending"},
                "registration_token": "reg-tok-123",
            },
        )
        resp = client.hosts.create(type="regular")
        assert isinstance(resp, CreateHostResponse)
        assert resp.registration_token == "reg-tok-123"

    @respx.mock
    def test_list(self, client):
        respx.get("https://api.wrenn.dev/v1/hosts").respond(
            200, json=[{"id": "h-1", "status": "online"}]
        )
        hosts = client.hosts.list()
        assert len(hosts) == 1
        assert isinstance(hosts[0], Host)

    @respx.mock
    def test_get(self, client):
        respx.get("https://api.wrenn.dev/v1/hosts/h-1").respond(
            200, json={"id": "h-1", "status": "online"}
        )
        resp = client.hosts.get("h-1")
        assert resp.id == "h-1"

    @respx.mock
    def test_delete(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/hosts/h-1").respond(204)
        client.hosts.delete("h-1")
        assert route.called

    @respx.mock
    def test_regenerate_token(self, client):
        respx.post("https://api.wrenn.dev/v1/hosts/h-1/token").respond(
            201,
            json={
                "host": {"id": "h-1"},
                "registration_token": "new-tok",
            },
        )
        resp = client.hosts.regenerate_token("h-1")
        assert resp.registration_token == "new-tok"

    @respx.mock
    def test_list_tags(self, client):
        respx.get("https://api.wrenn.dev/v1/hosts/h-1/tags").respond(
            200, json=["gpu", "high-mem"]
        )
        tags = client.hosts.list_tags("h-1")
        assert tags == ["gpu", "high-mem"]

    @respx.mock
    def test_add_tag(self, client):
        route = respx.post("https://api.wrenn.dev/v1/hosts/h-1/tags").respond(204)
        client.hosts.add_tag("h-1", "gpu")
        assert route.called

    @respx.mock
    def test_remove_tag(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/hosts/h-1/tags/gpu").respond(204)
        client.hosts.remove_tag("h-1", "gpu")
        assert route.called


class TestErrorHandling:
    @respx.mock
    def test_validation_error(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            400,
            json={"error": {"code": "invalid_request", "message": "bad input"}},
        )
        with pytest.raises(WrennValidationError) as exc_info:
            client.sandboxes.create()
        assert exc_info.value.code == "invalid_request"
        assert exc_info.value.status_code == 400

    @respx.mock
    def test_auth_error(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes").respond(
            401,
            json={"error": {"code": "unauthorized", "message": "bad key"}},
        )
        with pytest.raises(WrennAuthenticationError):
            client.sandboxes.list()

    @respx.mock
    def test_forbidden_error(self, client):
        respx.post("https://api.wrenn.dev/v1/hosts").respond(
            403,
            json={"error": {"code": "forbidden", "message": "nope"}},
        )
        with pytest.raises(WrennForbiddenError):
            client.hosts.create(type="regular")

    @respx.mock
    def test_not_found_error(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes/nope").respond(
            404,
            json={"error": {"code": "not_found", "message": "sandbox not found"}},
        )
        with pytest.raises(WrennNotFoundError):
            client.sandboxes.get("nope")

    @respx.mock
    def test_conflict_error(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes/sb-1").respond(
            409,
            json={"error": {"code": "invalid_state", "message": "not running"}},
        )
        with pytest.raises(WrennConflictError):
            client.sandboxes.get("sb-1")

    @respx.mock
    def test_host_has_sandboxes_error(self, client):
        respx.delete("https://api.wrenn.dev/v1/hosts/h-1").respond(
            409,
            json={
                "error": {
                    "code": "host_has_sandboxes",
                    "message": "host has running sandboxes",
                },
                "sandbox_ids": ["sb-1", "sb-2"],
            },
        )
        with pytest.raises(WrennHostHasSandboxesError) as exc_info:
            client.hosts.delete("h-1")
        assert exc_info.value.sandbox_ids == ["sb-1", "sb-2"]

    @respx.mock
    def test_agent_error(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            502,
            json={"error": {"code": "agent_error", "message": "host agent failed"}},
        )
        with pytest.raises(WrennAgentError):
            client.sandboxes.create()

    @respx.mock
    def test_internal_error(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes/sb-1").respond(
            500,
            json={"error": {"code": "internal_error", "message": "oops"}},
        )
        with pytest.raises(WrennInternalError):
            client.sandboxes.get("sb-1")

    @respx.mock
    def test_unknown_error_code_falls_back(self, client):
        respx.get("https://api.wrenn.dev/v1/sandboxes/sb-1").respond(
            418,
            json={"error": {"code": "teapot", "message": "I'm a teapot"}},
        )
        from wrenn.exceptions import WrennError

        with pytest.raises(WrennError) as exc_info:
            client.sandboxes.get("sb-1")
        assert exc_info.value.code == "teapot"


class TestAuthModes:
    def test_api_key_header(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            assert c._http.headers["X-API-Key"] == "wrn_test1234567890abcdef12345678"

    def test_token_header(self):
        with WrennClient(token="jwt-token-abc") as c:
            assert c._http.headers["Authorization"] == "Bearer jwt-token-abc"

    def test_no_auth_raises(self):
        with pytest.raises(ValueError, match="Either api_key or token"):
            WrennClient()

    @respx.mock
    def test_jwt_auth_on_api_keys(self):
        route = respx.get("https://api.wrenn.dev/v1/api-keys").respond(200, json=[])
        with WrennClient(token="jwt-abc") as c:
            c.api_keys.list()
        req = route.calls[0].request
        assert req.headers["Authorization"] == "Bearer jwt-abc"


class TestAsyncClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_sandboxes_create(self, async_client):
        async with async_client:
            respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
                201, json={"id": "sb-1", "status": "pending"}
            )
            resp = await async_client.sandboxes.create(template="base-python")
            assert resp.id == "sb-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_sandboxes_list(self, async_client):
        async with async_client:
            respx.get("https://api.wrenn.dev/v1/sandboxes").respond(
                200, json=[{"id": "sb-1"}]
            )
            boxes = await async_client.sandboxes.list()
            assert len(boxes) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_hosts_list(self, async_client):
        async with async_client:
            respx.get("https://api.wrenn.dev/v1/hosts").respond(200, json=[])
            hosts = await async_client.hosts.list()
            assert hosts == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_error_handling(self, async_client):
        async with async_client:
            respx.get("https://api.wrenn.dev/v1/sandboxes/nope").respond(
                404,
                json={"error": {"code": "not_found", "message": "not found"}},
            )
            with pytest.raises(WrennNotFoundError):
                await async_client.sandboxes.get("nope")
