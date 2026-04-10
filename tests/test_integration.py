from __future__ import annotations

import os
from typing import Generator

import pytest

from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.exceptions import WrennNotFoundError, WrennValidationError

WRENN_API_KEY = os.environ.get("WRENN_API_KEY")
WRENN_TOKEN = os.environ.get("WRENN_TOKEN")
WRENN_BASE_URL = os.environ.get("WRENN_BASE_URL", "http://localhost:8080")
WRENN_TEST_EMAIL = os.environ.get("WRENN_TEST_EMAIL")
WRENN_TEST_PASSWORD = os.environ.get("WRENN_TEST_PASSWORD")


def _has_auth() -> bool:
    return bool(WRENN_API_KEY or WRENN_TOKEN)


requires_auth = pytest.mark.skipif(
    not _has_auth(),
    reason="Set WRENN_API_KEY or WRENN_TOKEN to run integration tests",
)


@pytest.fixture
def client() -> Generator[WrennClient, None, None]:
    with WrennClient(
        api_key=WRENN_API_KEY,
        token=WRENN_TOKEN,
        base_url=WRENN_BASE_URL,
    ) as c:
        yield c


@pytest.fixture
def async_client() -> AsyncWrennClient:
    return AsyncWrennClient(
        api_key=WRENN_API_KEY,
        token=WRENN_TOKEN,
        base_url=WRENN_BASE_URL,
    )


@pytest.fixture
def bearer_client() -> Generator[WrennClient, None, None]:
    if WRENN_TOKEN:
        with WrennClient(token=WRENN_TOKEN, base_url=WRENN_BASE_URL) as c:
            yield c
    elif WRENN_TEST_EMAIL and WRENN_TEST_PASSWORD:
        with WrennClient(
            api_key=WRENN_API_KEY, token=WRENN_TOKEN, base_url=WRENN_BASE_URL
        ) as c:
            resp = c.auth.login(WRENN_TEST_EMAIL, WRENN_TEST_PASSWORD)
        with WrennClient(token=resp.token, base_url=WRENN_BASE_URL) as c:
            yield c
    else:
        pytest.skip(
            "Set WRENN_TOKEN or WRENN_TEST_EMAIL+WRENN_TEST_PASSWORD for bearer-auth tests"
        )


@requires_auth
class TestSandboxLifecycle:
    def test_create_exec_destroy(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            result = sb.exec("echo", args=["hello"])
            assert result.exit_code == 0
            assert "hello" in result.stdout

    def test_exec_with_args(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            result = sb.exec("echo", args=["hello", "world"])
            assert result.exit_code == 0
            assert "hello world" in result.stdout

    def test_exec_nonzero_exit(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            result = sb.exec("sh", args=["-c", "exit 42"])
            assert result.exit_code == 42

    def test_exec_stderr(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            result = sb.exec("sh", args=["-c", "echo err>&2"])
            assert result.exit_code == 0
            assert "err" in result.stderr

    def test_context_manager_cleanup(self, client):
        sb = client.sandboxes.create(template="minimal", timeout_sec=120)
        sb_id = sb.id

        with sb:
            sb.wait_ready(timeout=60, interval=1)

        fetched = client.sandboxes.get(sb_id)
        assert fetched.status in ("stopped", "destroyed")


@requires_auth
class TestFileIO:
    def test_upload_and_download(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            content = b"Hello from integration test!"
            sb.upload("/tmp/test_file.txt", content)
            downloaded = sb.download("/tmp/test_file.txt")
            assert downloaded == content

    def test_download_nonexistent_file(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            with pytest.raises(Exception):
                sb.download("/tmp/no_such_file_12345")


@requires_auth
class TestPauseResume:
    def test_pause_and_resume(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.pause()
            assert sb.status == "paused"

            sb.resume()
            sb.wait_ready(timeout=60, interval=1)

            result = sb.exec("echo", args=["resumed"])
            assert result.exit_code == 0
            assert "resumed" in result.stdout


@requires_auth
class TestPing:
    def test_ping_resets_timer(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.ping()
            result = sb.exec("echo", args=["still_alive"])
            assert result.exit_code == 0
            assert "still_alive" in result.stdout


@requires_auth
class TestProxy:
    def test_get_url(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            url = sb.get_url(8888)
            assert sb.id in url
            assert "8888" in url


@requires_auth
class TestListAndGet:
    def test_list_sandboxes(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            boxes = client.sandboxes.list()
            ids = [b.id for b in boxes]
            assert sb.id in ids

    def test_get_existing_sandbox(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            fetched = client.sandboxes.get(sb.id)
            assert fetched.id == sb.id
            assert fetched.status == "running"

    def test_get_nonexistent_sandbox(self, client):
        with pytest.raises((WrennNotFoundError, WrennValidationError)):
            client.sandboxes.get("cl-nonexistent00000000000000000")


@requires_auth
class TestSnapshots:
    def test_list_templates(self, client):
        templates = client.snapshots.list()
        assert isinstance(templates, list)


@requires_auth
class TestAPIKeys:
    def test_create_list_delete(self, bearer_client):
        key_resp = bearer_client.api_keys.create(name="integration-test-key")
        assert key_resp.name == "integration-test-key"
        assert key_resp.key is not None
        assert key_resp.id is not None

        try:
            keys = bearer_client.api_keys.list()
            ids = [k.id for k in keys]
            assert key_resp.id in ids
        finally:
            bearer_client.api_keys.delete(key_resp.id)


@requires_auth
class TestRunCode:
    def test_basic_execution(self, client):
        with client.sandboxes.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as sb:
            sb.wait_ready(timeout=60, interval=1)

            r = sb.run_code("x = 42")
            assert r.error is None

            r = sb.run_code("x * 2")
            assert r.text == "84"

    def test_state_persists(self, client):
        with client.sandboxes.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as sb:
            sb.wait_ready(timeout=60, interval=1)

            sb.run_code("def greet(name): return f'hello {name}'")
            r = sb.run_code("greet('sandbox')")
            assert "hello sandbox" in (r.text or "")

    def test_error_traceback(self, client):
        with client.sandboxes.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as sb:
            sb.wait_ready(timeout=60, interval=1)

            r = sb.run_code("1/0")
            assert r.error is not None
            assert "ZeroDivisionError" in r.error

    def test_stdout_capture(self, client):
        with client.sandboxes.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as sb:
            sb.wait_ready(timeout=60, interval=1)

            r = sb.run_code("print('hello from kernel')")
            assert "hello from kernel" in r.stdout


@requires_auth
class TestAsyncSandboxLifecycle:
    @pytest.mark.asyncio
    async def test_async_create_exec_destroy(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="minimal", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)
                result = await sb.async_exec("echo", args=["async_hello"])
                assert result.exit_code == 0
                assert "async_hello" in result.stdout
            finally:
                await sb.async_destroy()

    @pytest.mark.asyncio
    async def test_async_upload_download(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="minimal", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)
                content = b"Async upload test"
                await sb.async_upload("/tmp/async_test.txt", content)
                downloaded = await sb.async_download("/tmp/async_test.txt")
                assert downloaded == content
            finally:
                await sb.async_destroy()

    @pytest.mark.asyncio
    async def test_async_run_code(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="python-interpreter-v0-beta", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)
                r = await sb.async_run_code("42 * 2")
                assert r.text == "84"
            finally:
                await sb.async_destroy()
