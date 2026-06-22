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
    Actor,
    Capsule,
    CapsuleMetrics,
    CapsuleStats,
    MetricPoint,
    Resource,
    SSEEvent,
    Status,
    Template,
    UsageResponse,
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
            202,
            json={
                "id": "sb-1",
                "status": "starting",
                "template": "base-python",
                "vcpus": 2,
                "memory_mb": 1024,
            },
        )
        resp = client.capsules.create(template="base-python", vcpus=2, memory_mb=1024)
        assert isinstance(resp, Capsule)
        assert resp.id == "sb-1"
        assert resp.status == Status.starting

    @respx.mock
    def test_create_defaults(self, client):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-2", "status": "starting"}
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
        route = respx.delete(f"{BASE}/v1/capsules/sb-1").respond(202)
        client.capsules.destroy("sb-1")
        assert route.called

    @respx.mock
    def test_pause(self, client):
        respx.post(f"{BASE}/v1/capsules/sb-1/pause").respond(
            202, json={"id": "sb-1", "status": "pausing"}
        )
        resp = client.capsules.pause("sb-1")
        assert resp.status == Status.pausing

    @respx.mock
    def test_resume(self, client):
        respx.post(f"{BASE}/v1/capsules/sb-1/resume").respond(
            202, json={"id": "sb-1", "status": "resuming"}
        )
        resp = client.capsules.resume("sb-1")
        assert resp.status == Status.resuming

    @respx.mock
    def test_ping(self, client):
        route = respx.post(f"{BASE}/v1/capsules/sb-1/ping").respond(204)
        client.capsules.ping("sb-1")
        assert route.called

    @respx.mock
    def test_stats(self, client):
        route = respx.get(f"{BASE}/v1/capsules/stats").respond(
            200,
            json={
                "range": "6h",
                "current": {"running_count": 2, "vcpus_reserved": 4},
                "peaks": {"running_count": 9},
                "series": {"running": [1, 2, 2]},
            },
        )
        stats = client.capsules.stats(range="6h")
        assert "range=6h" in str(route.calls[0].request.url)
        assert stats.current and stats.current.running_count == 2
        assert stats.peaks and stats.peaks.running_count == 9

    @respx.mock
    def test_usage_passes_date_params(self, client):
        import datetime as _dt

        route = respx.get(f"{BASE}/v1/capsules/usage").respond(
            200, json={"from": "2026-06-01", "to": "2026-06-22", "points": []}
        )
        client.capsules.usage(from_=_dt.date(2026, 6, 1), to="2026-06-22")
        url = str(route.calls[0].request.url)
        assert "from=2026-06-01" in url
        assert "to=2026-06-22" in url

    @respx.mock
    def test_metrics(self, client):
        respx.get(f"{BASE}/v1/capsules/sb-1/metrics").respond(
            200,
            json={
                "sandbox_id": "sb-1",
                "range": "10m",
                "points": [{"timestamp_unix": 1, "cpu_pct": 12.5, "mem_bytes": 4096}],
            },
        )
        m = client.capsules.metrics("sb-1")
        assert m.sandbox_id == "sb-1"
        assert m.points and m.points[0].cpu_pct == 12.5
        assert isinstance(m, CapsuleMetrics)
        assert isinstance(m.points[0], MetricPoint)

    @respx.mock
    def test_stats_default_omits_range(self, client):
        route = respx.get(f"{BASE}/v1/capsules/stats").respond(
            200,
            json={"range": "1h", "current": {}, "peaks": {}, "series": {}},
        )
        stats = client.capsules.stats()
        assert "range=" not in str(route.calls[0].request.url)
        assert isinstance(stats, CapsuleStats)

    @respx.mock
    def test_usage_default_omits_params(self, client):
        route = respx.get(f"{BASE}/v1/capsules/usage").respond(200, json={"points": []})
        usage = client.capsules.usage()
        url = str(route.calls[0].request.url)
        assert "from=" not in url
        assert "to=" not in url
        assert isinstance(usage, UsageResponse)

    @respx.mock
    def test_metrics_default_omits_range(self, client):
        route = respx.get(f"{BASE}/v1/capsules/sb-1/metrics").respond(
            200, json={"sandbox_id": "sb-1", "points": []}
        )
        client.capsules.metrics("sb-1")
        assert "range=" not in str(route.calls[0].request.url)

    @respx.mock
    def test_metrics_not_found(self, client):
        respx.get(f"{BASE}/v1/capsules/nope/metrics").respond(
            404,
            json={"error": {"code": "not_found", "message": "capsule not found"}},
        )
        with pytest.raises(WrennNotFoundError):
            client.capsules.metrics("nope")

    @respx.mock
    def test_stats_auth_error(self, client):
        respx.get(f"{BASE}/v1/capsules/stats").respond(
            401,
            json={"error": {"code": "unauthorized", "message": "bad key"}},
        )
        with pytest.raises(WrennAuthenticationError):
            client.capsules.stats()

    @respx.mock
    def test_usage_string_dates(self, client):
        route = respx.get(f"{BASE}/v1/capsules/usage").respond(200, json={"points": []})
        client.capsules.usage(from_="2026-01-01", to="2026-01-31")
        url = str(route.calls[0].request.url)
        assert "from=2026-01-01" in url
        assert "to=2026-01-31" in url

    @respx.mock
    def test_usage_partial_dates(self, client):
        route = respx.get(f"{BASE}/v1/capsules/usage").respond(200, json={"points": []})
        client.capsules.usage(from_="2026-01-01")
        url = str(route.calls[0].request.url)
        assert "from=2026-01-01" in url
        assert "to=" not in url


class TestEvents:
    @respx.mock
    def test_stream_parses_sse_frames(self, client):
        body = (
            ": keepalive\n"
            "event: capsule.create\n"
            'data: {"event":"capsule.create","resource":{"id":"sb-1","type":"capsule"}}\n'
            "\n"
            "event: capsule.destroy\n"
            'data: {"event":"capsule.destroy","resource":{"id":"sb-1","type":"capsule"}}\n'
            "\n"
        )
        respx.get(f"{BASE}/v1/events/stream").respond(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )
        events = list(client.events.stream())
        assert [e.event.value for e in events] == [
            "capsule.create",
            "capsule.destroy",
        ]
        assert events[0].resource and events[0].resource.id == "sb-1"

    @respx.mock
    def test_stream_multiline_data(self, client):
        body = (
            "event: capsule.create\n"
            'data: {"event":"capsule.create",\n'
            'data:  "resource":{"id":"sb-1","type":"capsule"}}\n'
            "\n"
        )
        respx.get(f"{BASE}/v1/events/stream").respond(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )
        events = list(client.events.stream())
        assert len(events) == 1
        assert events[0].resource.id == "sb-1"

    @respx.mock
    def test_stream_skips_keepalive_only(self, client):
        body = ": keepalive\n\n: keepalive\n\n"
        respx.get(f"{BASE}/v1/events/stream").respond(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )
        assert list(client.events.stream()) == []

    @respx.mock
    def test_stream_ignores_incomplete_trailing_frame(self, client):
        body = (
            'data: {"event":"capsule.create","resource":{"id":"sb-1","type":"capsule"}}\n'
            "\n"
            'data: {"event":"capsule.destroy"'  # no closing brace, no blank line
        )
        respx.get(f"{BASE}/v1/events/stream").respond(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )
        events = list(client.events.stream())
        assert len(events) == 1
        assert events[0].event.value == "capsule.create"

    @respx.mock
    def test_stream_full_payload_round_trip(self, client):
        body = (
            'data: {"event":"capsule.create",'
            '"outcome":"success",'
            '"resource":{"id":"sb-1","type":"capsule"},'
            '"actor":{"type":"api_key","id":"key-1","name":"ci"},'
            '"metadata":{"reason":"manual"}}\n'
            "\n"
        )
        respx.get(f"{BASE}/v1/events/stream").respond(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )
        events = list(client.events.stream())
        assert len(events) == 1
        ev = events[0]
        assert isinstance(ev, SSEEvent)
        assert isinstance(ev.resource, Resource)
        assert isinstance(ev.actor, Actor)
        assert ev.actor.name == "ci"
        assert ev.metadata == {"reason": "manual"}

    @respx.mock
    def test_stream_raises_on_4xx(self, client):
        respx.get(f"{BASE}/v1/events/stream").respond(
            401,
            json={"error": {"code": "unauthorized", "message": "bad key"}},
        )
        with pytest.raises(WrennAuthenticationError):
            list(client.events.stream())


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
                202, json={"id": "sb-1", "status": "starting"}
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

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_stats(self, async_client):
        async with async_client:
            route = respx.get(f"{BASE}/v1/capsules/stats").respond(
                200,
                json={
                    "range": "24h",
                    "current": {"running_count": 1},
                    "peaks": {"running_count": 5},
                    "series": {"running": [1]},
                },
            )
            stats = await async_client.capsules.stats(range="24h")
            assert "range=24h" in str(route.calls[0].request.url)
            assert isinstance(stats, CapsuleStats)
            assert stats.current.running_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_usage(self, async_client):
        import datetime as _dt

        async with async_client:
            route = respx.get(f"{BASE}/v1/capsules/usage").respond(
                200,
                json={
                    "from": "2026-06-01",
                    "to": "2026-06-22",
                    "points": [
                        {
                            "date": "2026-06-01",
                            "cpu_minutes": 1.5,
                            "ram_mb_minutes": 200.0,
                        }
                    ],
                },
            )
            usage = await async_client.capsules.usage(
                from_=_dt.date(2026, 6, 1), to="2026-06-22"
            )
            url = str(route.calls[0].request.url)
            assert "from=2026-06-01" in url
            assert "to=2026-06-22" in url
            assert isinstance(usage, UsageResponse)
            assert usage.points and usage.points[0].cpu_minutes == 1.5

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_metrics(self, async_client):
        async with async_client:
            respx.get(f"{BASE}/v1/capsules/sb-1/metrics").respond(
                200,
                json={
                    "sandbox_id": "sb-1",
                    "range": "2h",
                    "points": [
                        {"timestamp_unix": 1, "cpu_pct": 33.0, "mem_bytes": 1024}
                    ],
                },
            )
            m = await async_client.capsules.metrics("sb-1", range="2h")
            assert isinstance(m, CapsuleMetrics)
            assert m.points[0].cpu_pct == 33.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_metrics_not_found(self, async_client):
        async with async_client:
            respx.get(f"{BASE}/v1/capsules/nope/metrics").respond(
                404,
                json={"error": {"code": "not_found", "message": "not found"}},
            )
            with pytest.raises(WrennNotFoundError):
                await async_client.capsules.metrics("nope")

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_events_stream(self, async_client):
        async with async_client:
            body = (
                ": keepalive\n"
                'data: {"event":"capsule.create","resource":{"id":"sb-1","type":"capsule"}}\n'
                "\n"
                'data: {"event":"capsule.destroy","resource":{"id":"sb-1","type":"capsule"}}\n'
                "\n"
            )
            respx.get(f"{BASE}/v1/events/stream").respond(
                200,
                headers={"content-type": "text/event-stream"},
                content=body,
            )
            events = [ev async for ev in async_client.events.stream()]
            assert [e.event.value for e in events] == [
                "capsule.create",
                "capsule.destroy",
            ]

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_events_raises_on_4xx(self, async_client):
        async with async_client:
            respx.get(f"{BASE}/v1/events/stream").respond(
                401,
                json={"error": {"code": "unauthorized", "message": "bad key"}},
            )
            with pytest.raises(WrennAuthenticationError):
                async for _ in async_client.events.stream():
                    pass

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_events_multiline_data(self, async_client):
        async with async_client:
            body = (
                'data: {"event":"capsule.create",\n'
                'data:  "resource":{"id":"sb-1","type":"capsule"}}\n'
                "\n"
            )
            respx.get(f"{BASE}/v1/events/stream").respond(
                200,
                headers={"content-type": "text/event-stream"},
                content=body,
            )
            events = [ev async for ev in async_client.events.stream()]
            assert len(events) == 1
            assert events[0].resource.id == "sb-1"


class TestPackageSurface:
    def test_version(self):
        import wrenn

        assert wrenn.__version__ == "0.3.0"

    def test_new_models_exported(self):
        import wrenn.models as m

        for name in (
            "Actor",
            "CapsuleMetrics",
            "CapsuleStats",
            "MetricPoint",
            "Resource",
            "SSEEvent",
            "UsageResponse",
        ):
            assert hasattr(m, name), name
            assert name in m.__all__


class TestClientResolution:
    def test_default_base_url_strips_app_subdomain(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            assert c._proxy_domain == "wrenn.dev"

    def test_custom_base_url_preserves_host(self):
        with WrennClient(
            api_key="wrn_test1234567890abcdef12345678",
            base_url="http://localhost:8080/api",
        ) as c:
            assert c._proxy_domain == "localhost:8080"

    def test_explicit_proxy_domain_wins(self):
        with WrennClient(
            api_key="wrn_test1234567890abcdef12345678",
            base_url="https://app.wrenn.dev/api",
            proxy_domain="custom.example.com",
        ) as c:
            assert c._proxy_domain == "custom.example.com"

    def test_env_proxy_domain(self, monkeypatch):
        monkeypatch.setenv("WRENN_PROXY_DOMAIN", "env.example.com")
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            assert c._proxy_domain == "env.example.com"

    def test_default_timeout(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
            t = c._http.timeout
            assert t.connect == 10.0
            assert t.read == 30.0

    def test_timeout_float_override(self):
        with WrennClient(api_key="wrn_test1234567890abcdef12345678", timeout=5.0) as c:
            assert c._http.timeout.connect == 5.0
