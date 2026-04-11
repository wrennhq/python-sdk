from __future__ import annotations


import pytest
import respx

from wrenn.client import WrennClient
from wrenn.sandbox import CodeResult, Sandbox, _build_proxy_url


@pytest.fixture
def client():
    with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
        yield c


class TestBuildProxyUrl:
    def test_https_production(self):
        url = _build_proxy_url("https://api.wrenn.dev", "cl-abc123", 8888)
        assert url == "wss://8888-cl-abc123.api.wrenn.dev"

    def test_http_localhost(self):
        url = _build_proxy_url("http://localhost:8080", "cl-abc123", 3000)
        assert url == "ws://3000-cl-abc123.localhost:8080"

    def test_https_custom_port(self):
        url = _build_proxy_url("https://api.example.com:9443", "sb-1", 8080)
        assert url == "wss://8080-sb-1.api.example.com:9443"

    def test_http_no_port(self):
        url = _build_proxy_url("http://192.168.1.1", "sb-2", 5000)
        assert url == "ws://5000-sb-2.192.168.1.1"


class TestSandboxGetUrl:
    @respx.mock
    def test_get_url_returns_proxy_url(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201, json={"id": "cl-abc", "status": "pending"}
        )
        sb = client.sandboxes.create(template="minimal")
        url = sb.get_url(8888)
        assert url == "wss://8888-cl-abc.api.wrenn.dev"

    @respx.mock
    def test_get_url_localhost(self):
        with WrennClient(
            api_key="wrn_test1234567890abcdef12345678",
            base_url="http://localhost:8080",
        ) as c:
            respx.post("http://localhost:8080/v1/sandboxes").respond(
                201, json={"id": "cl-xyz", "status": "pending"}
            )
            sb = c.sandboxes.create()
            url = sb.get_url(3000)
            assert url == "ws://3000-cl-xyz.localhost:8080"


class TestSandboxHttpClient:
    @respx.mock
    def test_http_client_has_api_key_header(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201, json={"id": "cl-abc", "status": "pending"}
        )
        sb = client.sandboxes.create()
        hc = sb.http_client
        assert hc.headers["X-API-Key"] == "wrn_test1234567890abcdef12345678"

    @respx.mock
    def test_http_client_sends_to_proxy(self, client):
        route = respx.get("https://8888-cl-abc.api.wrenn.dev/api/kernels").respond(
            200, json=[]
        )
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201, json={"id": "cl-abc", "status": "pending"}
        )
        sb = client.sandboxes.create()
        resp = sb.http_client.get("/api/kernels")
        assert resp.status_code == 200
        assert route.called

    def test_jwt_only_get_url_works(self):
        with WrennClient(token="jwt-abc") as c:
            sb = Sandbox(id="cl-abc")
            sb._bind(c._http, str(c._http.base_url), api_key=None, token="jwt-abc")
            url = sb.get_url(8888)
            assert "8888-cl-abc" in url

    def test_jwt_only_http_client_has_bearer_header(self):
        with WrennClient(token="jwt-abc") as c:
            sb = Sandbox(id="cl-abc")
            sb._bind(c._http, str(c._http.base_url), api_key=None, token="jwt-abc")
            hc = sb.http_client
            assert hc.headers["Authorization"] == "Bearer jwt-abc"


class TestCreateReturnsBoundSandbox:
    @respx.mock
    def test_create_returns_sandbox_subclass(self, client):
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201, json={"id": "cl-1", "status": "pending", "template": "minimal"}
        )
        sb = client.sandboxes.create(template="minimal")
        assert isinstance(sb, Sandbox)
        assert sb.id == "cl-1"
        assert hasattr(sb, "exec")
        assert hasattr(sb, "run_code")
        assert hasattr(sb, "get_url")

    @respx.mock
    def test_create_context_manager(self, client):
        route = respx.delete("https://api.wrenn.dev/v1/sandboxes/cl-1").respond(204)
        respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
            201, json={"id": "cl-1", "status": "pending"}
        )
        sb = client.sandboxes.create()
        with sb:
            assert sb.id == "cl-1"
        assert route.called


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


class TestJupyterMessageFormat:
    def test_execute_request_structure(self):
        sb = Sandbox(id="test")
        msg = sb._jupyter_execute_request("x = 42")
        assert msg["msg_type"] == "execute_request"
        assert msg["content"]["code"] == "x = 42"
        assert msg["content"]["silent"] is False
        assert "msg_id" in msg
        assert "header" in msg
        assert msg["header"]["msg_type"] == "execute_request"

    def test_execute_request_unique_ids(self):
        sb = Sandbox(id="test")
        m1 = sb._jupyter_execute_request("a")
        m2 = sb._jupyter_execute_request("b")
        assert m1["msg_id"] != m2["msg_id"]
