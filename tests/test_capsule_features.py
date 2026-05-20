from __future__ import annotations

import httpx
import pytest
import respx

from wrenn.capsule import Capsule, _build_http_proxy_url, _build_proxy_url
from wrenn.code_runner.models import Execution, ExecutionError, Logs, Result

BASE = "https://app.wrenn.dev/api"
API_KEY = "wrn_test1234567890abcdef12345678"


class TestBuildProxyUrl:
    def test_https_production(self):
        url = _build_proxy_url("https://app.wrenn.dev/api", "cl-abc123", 8888)
        assert url == "wss://8888-cl-abc123.app.wrenn.dev"

    def test_http_localhost(self):
        url = _build_proxy_url("http://localhost:8080", "cl-abc123", 3000)
        assert url == "ws://3000-cl-abc123.localhost:8080"

    def test_https_custom_port(self):
        url = _build_proxy_url("https://api.example.com:9443", "sb-1", 8080)
        assert url == "wss://8080-sb-1.api.example.com:9443"

    def test_http_no_port(self):
        url = _build_proxy_url("http://192.168.1.1", "sb-2", 5000)
        assert url == "ws://5000-sb-2.192.168.1.1"


class TestBuildHttpProxyUrl:
    """``get_url`` returns an HTTP(S) URL; ``/api`` path on the base URL is
    discarded — only the host is used to build the proxy subdomain."""

    def test_https_production_strips_api_path(self):
        url = _build_http_proxy_url("https://app.wrenn.dev/api", "cl-abc", 8080)
        assert url == "https://8080-cl-abc.app.wrenn.dev"

    def test_http_localhost_preserves_port(self):
        url = _build_http_proxy_url("http://localhost:8080/api", "cl-abc", 3000)
        assert url == "http://3000-cl-abc.localhost:8080"

    def test_https_custom_port(self):
        url = _build_http_proxy_url("https://api.example.com:9443", "sb-1", 80)
        assert url == "https://80-sb-1.api.example.com:9443"


class TestCapsuleCreate:
    @respx.mock
    def test_capsule_constructor_creates(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting", "template": "minimal"}
        )
        cap = Capsule(
            template="minimal",
            api_key="wrn_test1234567890abcdef12345678",
            base_url=BASE,
        )
        assert cap.capsule_id == "cl-1"
        assert hasattr(cap, "commands")
        assert hasattr(cap, "files")

    @respx.mock
    def test_capsule_create_classmethod(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-2", "status": "starting"}
        )
        cap = Capsule.create(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert cap.capsule_id == "cl-2"

    @respx.mock
    def test_capsule_context_manager_kills(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting"}
        )
        kill_route = respx.delete(f"{BASE}/v1/capsules/cl-1").respond(202)
        with Capsule(api_key="wrn_test1234567890abcdef12345678", base_url=BASE) as cap:
            assert cap.capsule_id == "cl-1"
        assert kill_route.called

    @respx.mock
    def test_capsule_env_var(self, monkeypatch):
        monkeypatch.setenv("WRENN_API_KEY", "wrn_from_env_key")
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-3", "status": "starting"}
        )
        cap = Capsule(base_url=BASE)
        assert cap.capsule_id == "cl-3"


class TestCapsuleStaticMethods:
    @respx.mock
    def test_static_destroy(self):
        route = respx.delete(f"{BASE}/v1/capsules/cl-1").respond(202)
        Capsule._static_destroy(
            "cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE
        )
        assert route.called

    @respx.mock
    def test_static_pause(self):
        respx.post(f"{BASE}/v1/capsules/cl-1/pause").respond(
            202, json={"id": "cl-1", "status": "pausing"}
        )
        info = Capsule._static_pause(
            "cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE
        )
        assert info.status.value == "pausing"

    @respx.mock
    def test_static_list(self):
        respx.get(f"{BASE}/v1/capsules").respond(
            200, json=[{"id": "cl-1", "status": "running"}]
        )
        items = Capsule.list(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert len(items) == 1
        assert items[0].id == "cl-1"

    @respx.mock
    def test_static_get_info(self):
        respx.get(f"{BASE}/v1/capsules/cl-1").respond(
            200, json={"id": "cl-1", "status": "running"}
        )
        info = Capsule._static_get_info(
            "cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE
        )
        assert info.id == "cl-1"


class TestCapsuleConnect:
    @respx.mock
    def test_connect_running(self):
        respx.get(f"{BASE}/v1/capsules/cl-1").respond(
            200, json={"id": "cl-1", "status": "running"}
        )
        cap = Capsule.connect(
            "cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE
        )
        assert cap.capsule_id == "cl-1"

    @respx.mock
    def test_connect_paused_resumes(self):
        get_route = respx.get(f"{BASE}/v1/capsules/cl-1")
        get_route.side_effect = [
            httpx.Response(200, json={"id": "cl-1", "status": "paused"}),
            httpx.Response(200, json={"id": "cl-1", "status": "running"}),
        ]
        respx.post(f"{BASE}/v1/capsules/cl-1/resume").respond(
            202, json={"id": "cl-1", "status": "resuming"}
        )
        cap = Capsule.connect(
            "cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE
        )
        assert cap.capsule_id == "cl-1"


class TestExecutionModels:
    def test_execution_defaults(self):
        e = Execution()
        assert e.results == []
        assert e.logs.stdout == []
        assert e.logs.stderr == []
        assert e.error is None
        assert e.text is None

    def test_result_from_bundle(self):
        bundle = {"text/plain": "84", "image/png": "base64data"}
        r = Result.from_bundle(bundle, is_main_result=True)
        assert r.text == "84"
        assert r.png == "base64data"
        assert r.is_main_result is True

    def test_result_from_bundle_preserves_text_plain(self):
        # ``text/plain`` is the Jupyter repr — preserved verbatim now.
        bundle = {"text/plain": "'hello'"}
        r = Result.from_bundle(bundle)
        assert r.text == "'hello'"

    def test_result_from_bundle_extra_mimes(self):
        bundle = {"text/plain": "x", "application/vnd.custom": "data"}
        r = Result.from_bundle(bundle)
        assert r.extra == {"application/vnd.custom": "data"}

    def test_result_formats(self):
        r = Result(text="hi", png="data")
        assert "text" in r.formats()
        assert "png" in r.formats()
        assert "html" not in r.formats()

    def test_execution_text_property(self):
        e = Execution(
            results=[
                Result(text="chart", is_main_result=False),
                Result(text="42", is_main_result=True),
            ]
        )
        assert e.text == "42"

    def test_execution_error(self):
        err = ExecutionError(
            name="ZeroDivisionError",
            value="division by zero",
            traceback="Traceback ...\nZeroDivisionError: division by zero",
        )
        e = Execution(error=err)
        assert e.error is not None
        assert "ZeroDivisionError" in e.error.name

    def test_logs(self):
        logs = Logs(stdout=["hello\n", "world\n"], stderr=["warn\n"])
        assert "".join(logs.stdout) == "hello\nworld\n"
        assert "".join(logs.stderr) == "warn\n"


class TestGetUrlPublic:
    """``Capsule.get_url`` returns the HTTP proxy URL."""

    @respx.mock
    def test_sync_get_url_default_base(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-99", "status": "starting"}
        )
        cap = Capsule(api_key=API_KEY, base_url=BASE)
        assert cap.get_url(8080) == "https://8080-cl-99.app.wrenn.dev"

    @respx.mock
    def test_sync_get_url_localhost(self):
        local_base = "http://localhost:8080/api"
        respx.post(f"{local_base}/v1/capsules").respond(
            202, json={"id": "cl-42", "status": "starting"}
        )
        cap = Capsule(api_key=API_KEY, base_url=local_base)
        assert cap.get_url(3000) == "http://3000-cl-42.localhost:8080"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_get_url(self):
        from wrenn.async_capsule import AsyncCapsule

        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-async", "status": "starting"}
        )
        cap = await AsyncCapsule.create(api_key=API_KEY, base_url=BASE)
        assert cap.get_url(5000) == "https://5000-cl-async.app.wrenn.dev"
        await cap._client.aclose()


class TestPtyConnect:
    """``pty_connect`` reconnects to an existing PTY session by tag."""

    def _capsule(self):
        with respx.mock:
            respx.post(f"{BASE}/v1/capsules").respond(
                202, json={"id": "cl-1", "status": "starting"}
            )
            return Capsule(api_key=API_KEY, base_url=BASE)

    def test_sync_pty_connect_sends_connect_frame(self):
        from unittest.mock import MagicMock, patch

        cap = self._capsule()
        ws = MagicMock()
        ctx = MagicMock()
        ctx.__enter__.return_value = ws
        ctx.__exit__.return_value = False

        with patch("wrenn.capsule.httpx_ws.connect_ws", return_value=ctx):
            with cap.pty_connect("tag-xyz") as session:
                assert session is not None
        # First send_text call must be a ``connect`` frame with the tag.
        import json as _json

        sent = ws.send_text.call_args_list[0].args[0]
        payload = _json.loads(sent)
        assert payload == {"type": "connect", "tag": "tag-xyz"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_pty_connect_sends_connect_frame(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from wrenn.async_capsule import AsyncCapsule

        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting"}
        )
        cap = await AsyncCapsule.create(api_key=API_KEY, base_url=BASE)
        ws = MagicMock()
        ws.send_text = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ws)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("wrenn.async_capsule.httpx_ws.aconnect_ws", return_value=ctx):
            async with cap.pty_connect("tag-async") as session:
                assert session is not None
        import json as _json

        sent = ws.send_text.call_args_list[0].args[0]
        payload = _json.loads(sent)
        assert payload == {"type": "connect", "tag": "tag-async"}
        await cap._client.aclose()


class TestCreateSnapshot:
    @respx.mock
    def test_sync_create_snapshot_posts_capsule_id(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting"}
        )
        snap_route = respx.post(f"{BASE}/v1/snapshots").respond(
            201,
            json={"name": "my-snap"},
        )
        cap = Capsule(api_key=API_KEY, base_url=BASE)
        tpl = cap.create_snapshot(name="my-snap", overwrite=True)
        import json as _json

        req = snap_route.calls[0].request
        body = _json.loads(req.content)
        assert body["sandbox_id"] == "cl-1"
        assert body["name"] == "my-snap"
        assert req.url.params["overwrite"] == "true"
        assert tpl.name == "my-snap"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_create_snapshot(self):
        from wrenn.async_capsule import AsyncCapsule

        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting"}
        )
        respx.post(f"{BASE}/v1/snapshots").respond(
            201,
            json={"name": "auto-named"},
        )
        cap = await AsyncCapsule.create(api_key=API_KEY, base_url=BASE)
        tpl = await cap.create_snapshot()
        assert tpl.name == "auto-named"
        await cap._client.aclose()


class TestUploadStreamChunked:
    """``upload_stream`` must declare ``Transfer-Encoding: chunked`` and
    deliver the multipart body without buffering."""

    @respx.mock
    def test_sync_upload_stream_chunked(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting"}
        )
        route = respx.post(f"{BASE}/v1/capsules/cl-1/files/stream/write").respond(
            200, json={}
        )
        cap = Capsule(api_key=API_KEY, base_url=BASE)

        def chunks():
            yield b"hello "
            yield b"world\n"

        cap.files.upload_stream("/tmp/out.txt", chunks())
        req = route.calls[0].request
        assert req.headers["transfer-encoding"] == "chunked"
        ct = req.headers["content-type"]
        assert ct.startswith("multipart/form-data; boundary=")
        body = bytes(req.content)
        assert b'name="path"' in body
        assert b"/tmp/out.txt" in body
        assert b'name="file"' in body
        assert b"hello world\n" in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_upload_stream_chunked(self):
        from wrenn.async_capsule import AsyncCapsule

        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "cl-1", "status": "starting"}
        )
        route = respx.post(f"{BASE}/v1/capsules/cl-1/files/stream/write").respond(
            200, json={}
        )
        cap = await AsyncCapsule.create(api_key=API_KEY, base_url=BASE)

        async def chunks():
            yield b"abc"
            yield b"def"

        await cap.files.upload_stream("/tmp/out.bin", chunks())
        req = route.calls[0].request
        assert req.headers["transfer-encoding"] == "chunked"
        body = bytes(req.content)
        assert b"abcdef" in body
        await cap._client.aclose()


class TestDeprecationWarnings:
    def test_import_sandbox_from_wrenn_warns(self):
        import sys
        import warnings

        # Clear cached attribute
        if "Sandbox" in dir(sys.modules.get("wrenn", object())):
            delattr(sys.modules["wrenn"], "Sandbox")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from wrenn import Sandbox

            assert Sandbox is Capsule
            fw = [x for x in w if issubclass(x.category, FutureWarning)]
            assert len(fw) >= 1
            assert "Sandbox" in str(fw[0].message)
