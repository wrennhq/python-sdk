from __future__ import annotations

import pytest
import respx

from wrenn.capsule import Capsule, _build_proxy_url
from wrenn.code_interpreter.capsule import CodeResult

BASE = "https://app.wrenn.dev/api"


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


class TestCapsuleCreate:
    @respx.mock
    def test_capsule_constructor_creates(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-1", "status": "pending", "template": "minimal"}
        )
        cap = Capsule(template="minimal", api_key="wrn_test1234567890abcdef12345678")
        assert cap.capsule_id == "cl-1"
        assert hasattr(cap, "commands")
        assert hasattr(cap, "files")

    @respx.mock
    def test_capsule_create_classmethod(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-2", "status": "pending"}
        )
        cap = Capsule.create(api_key="wrn_test1234567890abcdef12345678")
        assert cap.capsule_id == "cl-2"

    @respx.mock
    def test_capsule_context_manager_kills(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-1", "status": "pending"}
        )
        kill_route = respx.delete(f"{BASE}/v1/capsules/cl-1").respond(204)
        with Capsule(api_key="wrn_test1234567890abcdef12345678") as cap:
            assert cap.capsule_id == "cl-1"
        assert kill_route.called

    @respx.mock
    def test_capsule_env_var(self, monkeypatch):
        monkeypatch.setenv("WRENN_API_KEY", "wrn_from_env_key")
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-3", "status": "pending"}
        )
        cap = Capsule()
        assert cap.capsule_id == "cl-3"


class TestCapsuleStaticMethods:
    @respx.mock
    def test_static_destroy(self):
        route = respx.delete(f"{BASE}/v1/capsules/cl-1").respond(204)
        Capsule._static_destroy("cl-1", api_key="wrn_test1234567890abcdef12345678")
        assert route.called

    @respx.mock
    def test_static_pause(self):
        respx.post(f"{BASE}/v1/capsules/cl-1/pause").respond(
            200, json={"id": "cl-1", "status": "paused"}
        )
        info = Capsule._static_pause("cl-1", api_key="wrn_test1234567890abcdef12345678")
        assert info.status.value == "paused"

    @respx.mock
    def test_static_list(self):
        respx.get(f"{BASE}/v1/capsules").respond(
            200, json=[{"id": "cl-1", "status": "running"}]
        )
        items = Capsule.list(api_key="wrn_test1234567890abcdef12345678")
        assert len(items) == 1
        assert items[0].id == "cl-1"

    @respx.mock
    def test_static_get_info(self):
        respx.get(f"{BASE}/v1/capsules/cl-1").respond(
            200, json={"id": "cl-1", "status": "running"}
        )
        info = Capsule._static_get_info("cl-1", api_key="wrn_test1234567890abcdef12345678")
        assert info.id == "cl-1"


class TestCapsuleConnect:
    @respx.mock
    def test_connect_running(self):
        respx.get(f"{BASE}/v1/capsules/cl-1").respond(
            200, json={"id": "cl-1", "status": "running"}
        )
        cap = Capsule.connect("cl-1", api_key="wrn_test1234567890abcdef12345678")
        assert cap.capsule_id == "cl-1"

    @respx.mock
    def test_connect_paused_resumes(self):
        respx.get(f"{BASE}/v1/capsules/cl-1").respond(
            200, json={"id": "cl-1", "status": "paused"}
        )
        respx.post(f"{BASE}/v1/capsules/cl-1/resume").respond(
            200, json={"id": "cl-1", "status": "running"}
        )
        cap = Capsule.connect("cl-1", api_key="wrn_test1234567890abcdef12345678")
        assert cap.capsule_id == "cl-1"


class TestCodeResult:
    def test_defaults(self):
        r = CodeResult()
        assert r.text is None
        assert r.data is None
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.error is None

    def test_with_values(self):
        r = CodeResult(
            text="84",
            data={"text/plain": "84"},
            stdout="",
            stderr="",
            error=None,
        )
        assert r.text == "84"
        assert r.data["text/plain"] == "84"

    def test_error_result(self):
        r = CodeResult(error="ZeroDivisionError: division by zero\n...")
        assert r.error is not None
        assert "ZeroDivisionError" in r.error


class TestDeprecationWarnings:
    def test_import_sandbox_from_wrenn_warns(self):
        import importlib
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
