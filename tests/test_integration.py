from __future__ import annotations

import os
from typing import Generator

import pytest

from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.exceptions import WrennNotFoundError, WrennValidationError
from wrenn.pty import PtyEventType

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


@requires_auth
class TestFilesystemListDir:
    def test_list_dir_root(self, client: WrennClient):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.mkdir("/tmp/ls_test_root")
            sb.upload("/tmp/ls_test_root/hello.txt", b"hello")
            entries = sb.list_dir("/tmp/ls_test_root")
            assert isinstance(entries, list)
            names = [e.name for e in entries]
            assert "hello.txt" in names

    def test_list_dir_after_mkdir(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.mkdir("/tmp/fs_test_dir")
            entries = sb.list_dir("/tmp")
            names = [e.name for e in entries]
            assert "fs_test_dir" in names

    def test_list_dir_file_metadata(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.upload("/tmp/meta_test.txt", b"hello world")
            entries = sb.list_dir("/tmp")
            match = [e for e in entries if e.name == "meta_test.txt"]
            assert len(match) == 1
            f = match[0]
            assert f.type == "file"
            assert f.size == 11
            assert f.permissions is not None
            assert f.owner is not None
            assert f.group is not None
            assert f.modified_at is not None

    def test_list_dir_depth(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.mkdir("/tmp/depth_a/depth_b")
            sb.upload("/tmp/depth_a/depth_b/nested.txt", b"deep")
            entries = sb.list_dir("/tmp/depth_a", depth=2)
            paths = [e.path for e in entries]
            assert any("nested.txt" in p for p in paths)

    def test_list_dir_empty_directory(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.mkdir("/tmp/empty_dir_test")
            entries = sb.list_dir("/tmp/empty_dir_test")
            assert entries == []


@requires_auth
class TestFilesystemMkdir:
    def test_mkdir_creates_directory(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            entry = sb.mkdir("/tmp/mkdir_test")
            assert entry.name == "mkdir_test"
            assert entry.type == "directory"
            assert entry.path == "/tmp/mkdir_test"

    def test_mkdir_creates_parents(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            entry = sb.mkdir("/tmp/a/b/c/d")
            assert entry.type == "directory"

    def test_mkdir_already_exists(self, client: WrennClient):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.mkdir("/tmp/exist_test")
            entry = sb.mkdir("/tmp/exist_test")
            assert entry.type == "directory"


@requires_auth
class TestFilesystemRemove:
    def test_remove_file(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.upload("/tmp/rm_test.txt", b"delete me")
            entries_before = sb.list_dir("/tmp")
            assert any(e.name == "rm_test.txt" for e in entries_before)
            sb.remove("/tmp/rm_test.txt")
            entries_after = sb.list_dir("/tmp")
            assert not any(e.name == "rm_test.txt" for e in entries_after)

    def test_remove_directory(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            sb.mkdir("/tmp/rm_dir_test")
            sb.upload("/tmp/rm_dir_test/file.txt", b"inside")
            sb.remove("/tmp/rm_dir_test")
            entries = sb.list_dir("/tmp")
            assert not any(e.name == "rm_dir_test" for e in entries)

    def test_upload_download_remove_roundtrip(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            content = b"round trip test data " * 100
            sb.upload("/tmp/rt.txt", content)
            downloaded = sb.download("/tmp/rt.txt")
            assert downloaded == content
            sb.remove("/tmp/rt.txt")
            with pytest.raises(Exception):
                sb.download("/tmp/rt.txt")


@requires_auth
class TestStreamUploadDownload:
    def test_stream_upload_and_download(self, client: WrennClient):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            chunks = [b"chunk0_", b"chunk1_", b"chunk2"]

            def data_gen():
                yield from chunks

            sb.stream_upload("/tmp/stream_test.bin", data_gen())
            downloaded = sb.download("/tmp/stream_test.bin")
            assert downloaded == b"chunk0_chunk1_chunk2"

    def test_stream_download_large(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            content = b"x" * 65536 * 3
            sb.upload("/tmp/large.bin", content)
            collected = b""
            for chunk in sb.stream_download("/tmp/large.bin"):
                collected += chunk
            assert collected == content


@requires_auth
class TestPty:
    def test_pty_basic_output(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            with sb.pty(cmd="/bin/sh", cwd="/tmp") as term:
                term.write(b"echo pty_hello\n")
                output = b""
                for event in term:
                    if event.type == PtyEventType.output:
                        output += event.data
                    elif event.type == PtyEventType.exit:
                        break
                    if b"pty_hello" in output:
                        term.write(b"exit\n")
                assert b"pty_hello" in output

    def test_pty_tag_and_pid(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            with sb.pty(cmd="/bin/sh") as term:
                started = False
                for event in term:
                    if event.type == PtyEventType.started:
                        started = True
                        assert term.tag is not None
                        assert term.pid is not None
                        assert term.tag.startswith("pty-")
                    elif event.type == PtyEventType.output:
                        term.write(b"exit\n")
                    elif event.type == PtyEventType.exit:
                        break
                assert started

    def test_pty_exit_on_command_exit(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            with sb.pty(cmd="/bin/echo", args=["immediate"]) as term:
                events = list(term)
                types = [e.type for e in events]
                assert PtyEventType.started in types
                assert PtyEventType.output in types or PtyEventType.exit in types

    def test_pty_resize(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            with sb.pty(cmd="/bin/sh", cols=80, rows=24) as term:
                for event in term:
                    if event.type == PtyEventType.started:
                        term.resize(120, 40)
                        term.write(b"exit\n")
                    elif event.type == PtyEventType.exit:
                        break

    def test_pty_envs(self, client):
        with client.sandboxes.create(template="minimal", timeout_sec=120) as sb:
            sb.wait_ready(timeout=60, interval=1)
            with sb.pty(cmd="/bin/sh", envs={"MY_VAR": "hello_env"}) as term:
                output = b""
                for event in term:
                    if event.type == PtyEventType.started:
                        term.write(b"echo $MY_VAR\n")
                    elif event.type == PtyEventType.output:
                        output += event.data
                        if b"hello_env" in output:
                            term.write(b"exit\n")
                    elif event.type == PtyEventType.exit:
                        break
                assert b"hello_env" in output


@requires_auth
class TestAsyncFilesystem:
    @pytest.mark.asyncio
    async def test_async_list_dir(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="minimal", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)
                await sb.async_mkdir("/tmp/async_ls_test")
                await sb.async_upload("/tmp/async_ls_test/file.txt", b"data")
                entries = await sb.async_list_dir("/tmp/async_ls_test")
                assert isinstance(entries, list)
                assert any(e.name == "file.txt" for e in entries)
            finally:
                await sb.async_destroy()

    @pytest.mark.asyncio
    async def test_async_mkdir(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="minimal", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)
                entry = await sb.async_mkdir("/tmp/async_mkdir_test")
                assert entry.type == "directory"
                assert entry.name == "async_mkdir_test"
            finally:
                await sb.async_destroy()

    @pytest.mark.asyncio
    async def test_async_remove(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="minimal", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)
                await sb.async_upload("/tmp/async_rm.txt", b"bye")
                entries = await sb.async_list_dir("/tmp")
                assert any(e.name == "async_rm.txt" for e in entries)
                await sb.async_remove("/tmp/async_rm.txt")
                entries = await sb.async_list_dir("/tmp")
                assert not any(e.name == "async_rm.txt" for e in entries)
            finally:
                await sb.async_destroy()

    @pytest.mark.asyncio
    async def test_async_full_filesystem_roundtrip(self, async_client):
        async with async_client:
            sb = await async_client.sandboxes.create(
                template="minimal", timeout_sec=120
            )
            try:
                await sb.async_wait_ready(timeout=60, interval=1)

                await sb.async_mkdir("/tmp/async_rt")
                await sb.async_upload("/tmp/async_rt/file.txt", b"async content")
                entries = await sb.async_list_dir("/tmp/async_rt")
                assert any(e.name == "file.txt" for e in entries)

                data = await sb.async_download("/tmp/async_rt/file.txt")
                assert data == b"async content"

                await sb.async_remove("/tmp/async_rt/file.txt")
                entries = await sb.async_list_dir("/tmp/async_rt")
                assert not any(e.name == "file.txt" for e in entries)
            finally:
                await sb.async_destroy()
