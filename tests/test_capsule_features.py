from __future__ import annotations

import respx

from wrenn.capsule import Capsule, _build_proxy_url
from wrenn.code_interpreter.models import Execution, ExecutionError, Logs, Result

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
        cap = Capsule(template="minimal", api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert cap.capsule_id == "cl-1"
        assert hasattr(cap, "commands")
        assert hasattr(cap, "files")

    @respx.mock
    def test_capsule_create_classmethod(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-2", "status": "pending"}
        )
        cap = Capsule.create(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert cap.capsule_id == "cl-2"

    @respx.mock
    def test_capsule_context_manager_kills(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-1", "status": "pending"}
        )
        kill_route = respx.delete(f"{BASE}/v1/capsules/cl-1").respond(204)
        with Capsule(api_key="wrn_test1234567890abcdef12345678", base_url=BASE) as cap:
            assert cap.capsule_id == "cl-1"
        assert kill_route.called

    @respx.mock
    def test_capsule_env_var(self, monkeypatch):
        monkeypatch.setenv("WRENN_API_KEY", "wrn_from_env_key")
        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-3", "status": "pending"}
        )
        cap = Capsule(base_url=BASE)
        assert cap.capsule_id == "cl-3"


class TestCapsuleStaticMethods:
    @respx.mock
    def test_static_destroy(self):
        route = respx.delete(f"{BASE}/v1/capsules/cl-1").respond(204)
        Capsule._static_destroy("cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert route.called

    @respx.mock
    def test_static_pause(self):
        respx.post(f"{BASE}/v1/capsules/cl-1/pause").respond(
            200, json={"id": "cl-1", "status": "paused"}
        )
        info = Capsule._static_pause("cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert info.status.value == "paused"

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
        cap = Capsule.connect("cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert cap.capsule_id == "cl-1"

    @respx.mock
    def test_connect_paused_resumes(self):
        respx.get(f"{BASE}/v1/capsules/cl-1").respond(
            200, json={"id": "cl-1", "status": "paused"}
        )
        respx.post(f"{BASE}/v1/capsules/cl-1/resume").respond(
            200, json={"id": "cl-1", "status": "running"}
        )
        cap = Capsule.connect("cl-1", api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
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

    def test_result_from_bundle_strips_quotes(self):
        bundle = {"text/plain": "'hello'"}
        r = Result.from_bundle(bundle)
        assert r.text == "hello"

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
