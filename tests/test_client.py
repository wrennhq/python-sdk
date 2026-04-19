from __future__ import annotations

import pytest
import respx

from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.exceptions import (
    WrennAgentError,
    WrennAuthenticationError,
    WrennConflictError,
    WrennForbiddenError,
    WrennHostHasCapsulesError,
    WrennInternalError,
    WrennNotFoundError,
    WrennValidationError,
)
from wrenn.models import (
    APIKeyResponse,
    Capsule,
    CreateHostResponse,
    Host,
    SignupResponse,
    Status,
    Template,
    UsageResponse,
)


@pytest.fixture
def client():
    with WrennClient(
        api_key="wrn_test1234567890abcdef12345678", token="jwt-test-token-abc123"
    ) as c:
        yield c


@pytest.fixture
def async_client():
    return AsyncWrennClient(
        api_key="wrn_test1234567890abcdef12345678", token="jwt-test-token-abc123"
    )


class TestAuth:
    @respx.mock
    def test_signup(self, client):
        respx.post("https://api.wrenn.dev/v1/auth/signup").respond(
            201,
            json={"message": "Account created. Check your email to activate."},
        )
        resp = client.auth.signup("a@b.com", "password123", "Test User")
        assert isinstance(resp, SignupResponse)
        assert resp.message is not None

    @respx.mock
    def test_signup_no_creds(self):
        respx.post("https://api.wrenn.dev/v1/auth/signup").respond(
            201,
            json={"message": "Account created."},
        )
        with WrennClient() as c:
            resp = c.auth.signup("a@b.com", "password123", "Test User")
            assert isinstance(resp, SignupResponse)

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


class TestCapsules:
    @respx.mock
    def test_create(self, client):
        respx.post("https://api.wrenn.dev/v1/capsules").respond(
            201,
            json={
                "id": "sb-1",
                "status": "pending",
                "template": "base-python",
                "vcpus": 2,
                "memory_mb": 1024,
            },
        )
        resp = client.capsules.create(template="base-python", vcpus=2, memory_mb=1024)
        assert isinstance(resp, Capsule)
        assert resp.id == "sb-1"
        assert resp.status == Status.pending

    @respx.mock
    def test_create_defaults(self, client):
        respx.post("https://api.wrenn.dev/v1/capsules").respond(
            201, json={"id": "sb-2", "status": "pending"}
        )
        resp = client.capsules.create()
        assert resp.id == "sb-2"

    @respx.mock
    def test_list(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules").respond(
            200, json=[{"id": "sb-1", "status": "running"}]
        )
        boxes = client.capsules.list()
        assert len(boxes) == 1
        assert boxes[0].status == Status.running

    @respx.mock
    def test_get(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules/sb-1").respond(
            200, json={"id": "sb-1", "status": "running"}
        )
        resp = client.capsules.get("sb-1")
        assert resp.id == "sb-1"

    @respx.mock
    def test_destroy(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/capsules/sb-1").respond(204)
        client.capsules.destroy("sb-1")
        assert route.called

    @respx.mock
    def test_usage(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules/usage").respond(
            200,
            json={
                "from": "2026-03-21",
                "to": "2026-04-20",
                "points": [
                    {
                        "date": "2026-04-19",
                        "cpu_minutes": 12.5,
                        "ram_mb_minutes": 640.0,
                    },
                    {"date": "2026-04-20", "cpu_minutes": 8.0, "ram_mb_minutes": 512.0},
                ],
            },
        )
        resp = client.capsules.usage()
        assert isinstance(resp, UsageResponse)
        assert resp.points is not None
        assert len(resp.points) == 2
        assert resp.points[0].cpu_minutes == 12.5

    @respx.mock
    def test_usage_with_dates(self, client):
        route = respx.get("https://api.wrenn.dev/v1/capsules/usage").respond(
            200,
            json={"from": "2026-04-01", "to": "2026-04-15", "points": []},
        )
        client.capsules.usage(from_date="2026-04-01", to_date="2026-04-15")
        req = route.calls[0].request
        assert "from=2026-04-01" in str(req.url)
        assert "to=2026-04-15" in str(req.url)


class TestSnapshots:
    @respx.mock
    def test_create(self, client):
        respx.post("https://api.wrenn.dev/v1/snapshots").respond(
            201,
            json={"name": "snap-1", "type": "snapshot", "vcpus": 1},
        )
        resp = client.snapshots.create(capsule_id="sb-1", name="snap-1")
        assert isinstance(resp, Template)
        assert resp.name == "snap-1"

    @respx.mock
    def test_create_with_overwrite(self, client):
        route = respx.post("https://api.wrenn.dev/v1/snapshots").respond(
            201, json={"name": "snap-1", "type": "snapshot"}
        )
        client.snapshots.create(capsule_id="sb-1", overwrite=True)
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
        respx.post("https://api.wrenn.dev/v1/capsules").respond(
            400,
            json={"error": {"code": "invalid_request", "message": "bad input"}},
        )
        with pytest.raises(WrennValidationError) as exc_info:
            client.capsules.create()
        assert exc_info.value.code == "invalid_request"
        assert exc_info.value.status_code == 400

    @respx.mock
    def test_auth_error(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules").respond(
            401,
            json={"error": {"code": "unauthorized", "message": "bad key"}},
        )
        with pytest.raises(WrennAuthenticationError):
            client.capsules.list()

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
        respx.get("https://api.wrenn.dev/v1/capsules/nope").respond(
            404,
            json={"error": {"code": "not_found", "message": "capsule not found"}},
        )
        with pytest.raises(WrennNotFoundError):
            client.capsules.get("nope")

    @respx.mock
    def test_conflict_error(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules/sb-1").respond(
            409,
            json={"error": {"code": "invalid_state", "message": "not running"}},
        )
        with pytest.raises(WrennConflictError):
            client.capsules.get("sb-1")

    @respx.mock
    def test_host_has_capsules_error(self, client):
        respx.delete("https://api.wrenn.dev/v1/hosts/h-1").respond(
            409,
            json={
                "error": {
                    "code": "host_has_capsules",
                    "message": "host has running capsules",
                },
                "sandbox_ids": ["sb-1", "sb-2"],
            },
        )
        with pytest.raises(WrennHostHasCapsulesError) as exc_info:
            client.hosts.delete("h-1")
        assert exc_info.value.capsule_ids == ["sb-1", "sb-2"]

    @respx.mock
    def test_agent_error(self, client):
        respx.post("https://api.wrenn.dev/v1/capsules").respond(
            502,
            json={"error": {"code": "agent_error", "message": "host agent failed"}},
        )
        with pytest.raises(WrennAgentError):
            client.capsules.create()

    @respx.mock
    def test_internal_error(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules/sb-1").respond(
            500,
            json={"error": {"code": "internal_error", "message": "oops"}},
        )
        with pytest.raises(WrennInternalError):
            client.capsules.get("sb-1")

    @respx.mock
    def test_unknown_error_code_falls_back(self, client):
        respx.get("https://api.wrenn.dev/v1/capsules/sb-1").respond(
            418,
            json={"error": {"code": "teapot", "message": "I'm a teapot"}},
        )
        from wrenn.exceptions import WrennError

        with pytest.raises(WrennError) as exc_info:
            client.capsules.get("sb-1")
        assert exc_info.value.code == "teapot"


class TestAuthModes:
    def test_api_key_only_creates_data_client(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            assert c._data_http is not None
            assert (
                c._data_http.headers["X-API-Key"] == "wrn_test1234567890abcdef12345678"
            )
            assert c._mgmt_http is None

    def test_token_only_creates_mgmt_client(self):
        with WrennClient(token="jwt-token-abc") as c:
            assert c._mgmt_http is not None
            assert c._mgmt_http.headers["Authorization"] == "Bearer jwt-token-abc"
            assert c._data_http is None

    def test_no_auth_allowed(self):
        with WrennClient() as c:
            assert c._data_http is None
            assert c._mgmt_http is None
            assert c._public_http is not None

    def test_both_creds_creates_both_clients(self):
        with WrennClient(
            api_key="wrn_test1234567890abcdef12345678", token="jwt-abc"
        ) as c:
            assert c._data_http is not None
            assert c._mgmt_http is not None

    def test_capsule_ops_require_api_key(self):
        with WrennClient(token="jwt-abc") as c:
            with pytest.raises(ValueError, match="API key"):
                c.capsules.list()

    def test_snapshot_ops_require_api_key(self):
        with WrennClient(token="jwt-abc") as c:
            with pytest.raises(ValueError, match="API key"):
                c.snapshots.list()

    def test_mgmt_ops_require_token(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            with pytest.raises(ValueError, match="JWT token"):
                c.api_keys.list()
            with pytest.raises(ValueError, match="JWT token"):
                c.teams.list()
            with pytest.raises(ValueError, match="JWT token"):
                c.hosts.list()
            with pytest.raises(ValueError, match="JWT token"):
                c.channels.list()
            with pytest.raises(ValueError, match="JWT token"):
                c.users.search("a@b.com")
            with pytest.raises(ValueError, match="JWT token"):
                c.account.get()
            with pytest.raises(ValueError, match="JWT token"):
                c.auth.switch_team("team-1")

    @respx.mock
    def test_mgmt_sends_bearer_only(self):
        route = respx.get("https://api.wrenn.dev/v1/api-keys").respond(200, json=[])
        with WrennClient(
            api_key="wrn_test1234567890abcdef12345678", token="jwt-abc"
        ) as c:
            c.api_keys.list()
        req = route.calls[0].request
        assert req.headers["Authorization"] == "Bearer jwt-abc"
        assert "X-API-Key" not in req.headers

    @respx.mock
    def test_data_sends_api_key_only(self):
        route = respx.get("https://api.wrenn.dev/v1/capsules").respond(200, json=[])
        with WrennClient(
            api_key="wrn_test1234567890abcdef12345678", token="jwt-abc"
        ) as c:
            c.capsules.list()
        req = route.calls[0].request
        assert req.headers["X-API-Key"] == "wrn_test1234567890abcdef12345678"
        assert "Authorization" not in req.headers

    @respx.mock
    def test_public_sends_no_auth(self):
        route = respx.post("https://api.wrenn.dev/v1/auth/signup").respond(
            201, json={"message": "ok"}
        )
        with WrennClient() as c:
            c.auth.signup("a@b.com", "password123", "Test")
        req = route.calls[0].request
        assert "X-API-Key" not in req.headers
        assert "Authorization" not in req.headers


class TestAsyncClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_capsules_create(self, async_client):
        async with async_client:
            respx.post("https://api.wrenn.dev/v1/capsules").respond(
                201, json={"id": "sb-1", "status": "pending"}
            )
            resp = await async_client.capsules.create(template="base-python")
            assert resp.id == "sb-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_capsules_list(self, async_client):
        async with async_client:
            respx.get("https://api.wrenn.dev/v1/capsules").respond(
                200, json=[{"id": "sb-1"}]
            )
            boxes = await async_client.capsules.list()
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
            respx.get("https://api.wrenn.dev/v1/capsules/nope").respond(
                404,
                json={"error": {"code": "not_found", "message": "not found"}},
            )
            with pytest.raises(WrennNotFoundError):
                await async_client.capsules.get("nope")
