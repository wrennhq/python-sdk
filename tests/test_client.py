from __future__ import annotations

import pytest
import respx

from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.exceptions import (
    WrennAgentError,
    WrennAuthenticationError,
    WrennConflictError,
    WrennInternalError,
    WrennNotFoundError,
    WrennValidationError,
)
from wrenn.models import (
    Capsule,
    Status,
    Template,
)

BASE = "https://app.wrenn.dev/api"


@pytest.fixture
def client():
    with WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE) as c:
        yield c


@pytest.fixture
def async_client():
    return AsyncWrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)


class TestCapsules:
    @respx.mock
    def test_create(self, client):
        respx.post(f"{BASE}/v1/capsules").respond(
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
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "sb-2", "status": "pending"}
        )
        resp = client.capsules.create()
        assert resp.id == "sb-2"

    @respx.mock
    def test_list(self, client):
        respx.get(f"{BASE}/v1/capsules").respond(
            200, json=[{"id": "sb-1", "status": "running"}]
        )
        boxes = client.capsules.list()
        assert len(boxes) == 1
        assert boxes[0].status == Status.running

    @respx.mock
    def test_get(self, client):
        respx.get(f"{BASE}/v1/capsules/sb-1").respond(
            200, json={"id": "sb-1", "status": "running"}
        )
        resp = client.capsules.get("sb-1")
        assert resp.id == "sb-1"

    @respx.mock
    def test_destroy(self, client):
        route = respx.delete(f"{BASE}/v1/capsules/sb-1").respond(204)
        client.capsules.destroy("sb-1")
        assert route.called

    @respx.mock
    def test_pause(self, client):
        respx.post(f"{BASE}/v1/capsules/sb-1/pause").respond(
            200, json={"id": "sb-1", "status": "paused"}
        )
        resp = client.capsules.pause("sb-1")
        assert resp.status == Status.paused

    @respx.mock
    def test_resume(self, client):
        respx.post(f"{BASE}/v1/capsules/sb-1/resume").respond(
            200, json={"id": "sb-1", "status": "running"}
        )
        resp = client.capsules.resume("sb-1")
        assert resp.status == Status.running

    @respx.mock
    def test_ping(self, client):
        route = respx.post(f"{BASE}/v1/capsules/sb-1/ping").respond(204)
        client.capsules.ping("sb-1")
        assert route.called


class TestSnapshots:
    @respx.mock
    def test_create(self, client):
        respx.post(f"{BASE}/v1/snapshots").respond(
            201,
            json={"name": "snap-1", "type": "snapshot", "vcpus": 1},
        )
        resp = client.snapshots.create(capsule_id="sb-1", name="snap-1")
        assert isinstance(resp, Template)
        assert resp.name == "snap-1"

    @respx.mock
    def test_create_with_overwrite(self, client):
        route = respx.post(f"{BASE}/v1/snapshots").respond(
            201, json={"name": "snap-1", "type": "snapshot"}
        )
        client.snapshots.create(capsule_id="sb-1", overwrite=True)
        req = route.calls[0].request
        assert "overwrite=true" in str(req.url)

    @respx.mock
    def test_list(self, client):
        respx.get(f"{BASE}/v1/snapshots").respond(
            200, json=[{"name": "base-python", "type": "base"}]
        )
        snaps = client.snapshots.list()
        assert len(snaps) == 1

    @respx.mock
    def test_list_with_filter(self, client):
        route = respx.get(f"{BASE}/v1/snapshots").respond(200, json=[])
        client.snapshots.list(type="snapshot")
        req = route.calls[0].request
        assert "type=snapshot" in str(req.url)

    @respx.mock
    def test_delete(self, client):
        route = respx.delete(f"{BASE}/v1/snapshots/snap-1").respond(204)
        client.snapshots.delete("snap-1")
        assert route.called


class TestErrorHandling:
    @respx.mock
    def test_validation_error(self, client):
        respx.post(f"{BASE}/v1/capsules").respond(
            400,
            json={"error": {"code": "invalid_request", "message": "bad input"}},
        )
        with pytest.raises(WrennValidationError) as exc_info:
            client.capsules.create()
        assert exc_info.value.code == "invalid_request"
        assert exc_info.value.status_code == 400

    @respx.mock
    def test_auth_error(self, client):
        respx.get(f"{BASE}/v1/capsules").respond(
            401,
            json={"error": {"code": "unauthorized", "message": "bad key"}},
        )
        with pytest.raises(WrennAuthenticationError):
            client.capsules.list()

    @respx.mock
    def test_not_found_error(self, client):
        respx.get(f"{BASE}/v1/capsules/nope").respond(
            404,
            json={"error": {"code": "not_found", "message": "capsule not found"}},
        )
        with pytest.raises(WrennNotFoundError):
            client.capsules.get("nope")

    @respx.mock
    def test_conflict_error(self, client):
        respx.get(f"{BASE}/v1/capsules/sb-1").respond(
            409,
            json={"error": {"code": "invalid_state", "message": "not running"}},
        )
        with pytest.raises(WrennConflictError):
            client.capsules.get("sb-1")

    @respx.mock
    def test_agent_error(self, client):
        respx.post(f"{BASE}/v1/capsules").respond(
            502,
            json={"error": {"code": "agent_error", "message": "host agent failed"}},
        )
        with pytest.raises(WrennAgentError):
            client.capsules.create()

    @respx.mock
    def test_internal_error(self, client):
        respx.get(f"{BASE}/v1/capsules/sb-1").respond(
            500,
            json={"error": {"code": "internal_error", "message": "oops"}},
        )
        with pytest.raises(WrennInternalError):
            client.capsules.get("sb-1")

    @respx.mock
    def test_unknown_error_code_falls_back(self, client):
        respx.get(f"{BASE}/v1/capsules/sb-1").respond(
            418,
            json={"error": {"code": "teapot", "message": "I'm a teapot"}},
        )
        from wrenn.exceptions import WrennError

        with pytest.raises(WrennError) as exc_info:
            client.capsules.get("sb-1")
        assert exc_info.value.code == "teapot"


class TestAuthModes:
    def test_api_key_header(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            assert c._http.headers["X-API-Key"] == "wrn_test1234567890abcdef12345678"

    def test_no_auth_raises(self, monkeypatch):
        monkeypatch.delenv("WRENN_API_KEY", raising=False)
        with pytest.raises(ValueError, match="No API key"):
            WrennClient()

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("WRENN_API_KEY", "wrn_from_env")
        with WrennClient() as c:
            assert c._http.headers["X-API-Key"] == "wrn_from_env"


class TestAsyncClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_capsules_create(self, async_client):
        async with async_client:
            respx.post(f"{BASE}/v1/capsules").respond(
                201, json={"id": "sb-1", "status": "pending"}
            )
            resp = await async_client.capsules.create(template="base-python")
            assert resp.id == "sb-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_capsules_list(self, async_client):
        async with async_client:
            respx.get(f"{BASE}/v1/capsules").respond(200, json=[{"id": "sb-1"}])
            boxes = await async_client.capsules.list()
            assert len(boxes) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_error_handling(self, async_client):
        async with async_client:
            respx.get(f"{BASE}/v1/capsules/nope").respond(
                404,
                json={"error": {"code": "not_found", "message": "not found"}},
            )
            with pytest.raises(WrennNotFoundError):
                await async_client.capsules.get("nope")
