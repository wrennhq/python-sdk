from __future__ import annotations

from wrenn.client import WrennClient

from .conftest import requires_auth


@requires_auth
class TestRunCode:
    def test_basic_execution(self, client: WrennClient):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            r = cap.run_code("x = 42")
            assert r.error is None

            r = cap.run_code("x * 2")
            assert r.text == "84"

    def test_state_persists(self, client: WrennClient):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            cap.run_code("def greet(name): return f'hello {name}'")
            r = cap.run_code("greet('capsule')")
            assert "hello capsule" in (r.text or "")

    def test_error_traceback(self, client: WrennClient):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            r = cap.run_code("1/0")
            assert r.error is not None
            assert "ZeroDivisionError" in r.error

    def test_stdout_capture(self, client: WrennClient):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            r = cap.run_code("print('hello from kernel')")
            assert "hello from kernel" in r.stdout
