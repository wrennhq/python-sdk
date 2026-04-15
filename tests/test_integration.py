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
class TestCapsuleLifecycle:
    def test_create_exec_destroy(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            result = cap.exec("echo", args=["hello"])
            assert result.exit_code == 0
            assert "hello" in result.stdout

    def test_exec_with_args(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            result = cap.exec("echo", args=["hello", "world"])
            assert result.exit_code == 0
            assert "hello world" in result.stdout

    def test_exec_nonzero_exit(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            result = cap.exec("sh", args=["-c", "exit 42"])
            assert result.exit_code == 42

    def test_exec_stderr(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            result = cap.exec("sh", args=["-c", "echo err>&2"])
            assert result.exit_code == 0
            assert "err" in result.stderr

    def test_context_manager_cleanup(self, client):
        cap = client.capsules.create(template="minimal", timeout_sec=120)
        cap_id = cap.id

        with cap:
            cap.wait_ready(timeout=60, interval=1)

        fetched = client.capsules.get(cap_id)
        assert fetched.status in ("stopped", "destroyed")


@requires_auth
class TestFileIO:
    def test_upload_and_download(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            content = b"Hello from integration test!"
            cap.upload("/tmp/test_file.txt", content)
            downloaded = cap.download("/tmp/test_file.txt")
            assert downloaded == content

    def test_download_nonexistent_file(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with pytest.raises(Exception):
                cap.download("/tmp/no_such_file_12345")


@requires_auth
class TestPauseResume:
    def test_pause_and_resume(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.pause()
            assert cap.status == "paused"

            cap.resume()
            cap.wait_ready(timeout=60, interval=1)

            result = cap.exec("echo", args=["resumed"])
            assert result.exit_code == 0
            assert "resumed" in result.stdout


@requires_auth
class TestPing:
    def test_ping_resets_timer(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.ping()
            result = cap.exec("echo", args=["still_alive"])
            assert result.exit_code == 0
            assert "still_alive" in result.stdout


@requires_auth
class TestProxy:
    def test_get_url(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            url = cap.get_url(8888)
            assert cap.id in url
            assert "8888" in url


@requires_auth
class TestListAndGet:
    def test_list_capsules(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            boxes = client.capsules.list()
            ids = [b.id for b in boxes]
            assert cap.id in ids

    def test_get_existing_capsule(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            fetched = client.capsules.get(cap.id)
            assert fetched.id == cap.id
            assert fetched.status == "running"

    def test_get_nonexistent_capsule(self, client):
        with pytest.raises((WrennNotFoundError, WrennValidationError)):
            client.capsules.get("cl-nonexistent00000000000000000")


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
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            r = cap.run_code("x = 42")
            assert r.error is None

            r = cap.run_code("x * 2")
            assert r.text == "84"

    def test_state_persists(self, client):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            cap.run_code("def greet(name): return f'hello {name}'")
            r = cap.run_code("greet('capsule')")
            assert "hello capsule" in (r.text or "")

    def test_error_traceback(self, client):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            r = cap.run_code("1/0")
            assert r.error is not None
            assert "ZeroDivisionError" in r.error

    def test_stdout_capture(self, client):
        with client.capsules.create(
            template="python-interpreter-v0-beta", timeout_sec=120
        ) as cap:
            cap.wait_ready(timeout=60, interval=1)

            r = cap.run_code("print('hello from kernel')")
            assert "hello from kernel" in r.stdout


@requires_auth
class TestAsyncCapsuleLifecycle:
    @pytest.mark.asyncio
    async def test_async_create_exec_destroy(self, async_client):
        async with async_client:
            cap = await async_client.capsules.create(
                template="minimal", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)
                result = await cap.async_exec("echo", args=["async_hello"])
                assert result.exit_code == 0
                assert "async_hello" in result.stdout
            finally:
                await cap.async_destroy()

    @pytest.mark.asyncio
    async def test_async_upload_download(self, async_client):
        async with async_client:
            cap = await async_client.capsules.create(
                template="minimal", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)
                content = b"Async upload test"
                await cap.async_upload("/tmp/async_test.txt", content)
                downloaded = await cap.async_download("/tmp/async_test.txt")
                assert downloaded == content
            finally:
                await cap.async_destroy()

    @pytest.mark.asyncio
    async def test_async_run_code(self, async_client):
        async with async_client:
            cap = await async_client.capsules.create(
                template="python-interpreter-v0-beta", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)
                r = await cap.async_run_code("42 * 2")
                assert r.text == "84"
            finally:
                await cap.async_destroy()


@requires_auth
class TestFilesystemListDir:
    def test_list_dir_root(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/ls_test_root")
            cap.upload("/tmp/ls_test_root/hello.txt", b"hello")
            entries = cap.list_dir("/tmp/ls_test_root")
            assert isinstance(entries, list)
            names = [e.name for e in entries]
            assert "hello.txt" in names

    def test_list_dir_after_mkdir(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/fs_test_dir")
            entries = cap.list_dir("/tmp")
            names = [e.name for e in entries]
            assert "fs_test_dir" in names

    def test_list_dir_file_metadata(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.upload("/tmp/meta_test.txt", b"hello world")
            entries = cap.list_dir("/tmp")
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
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/depth_a/depth_b")
            cap.upload("/tmp/depth_a/depth_b/nested.txt", b"deep")
            entries = cap.list_dir("/tmp/depth_a", depth=2)
            paths = [e.path for e in entries]
            assert any("nested.txt" in p for p in paths)

    def test_list_dir_empty_directory(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/empty_dir_test")
            entries = cap.list_dir("/tmp/empty_dir_test")
            assert entries == []


@requires_auth
class TestFilesystemMkdir:
    def test_mkdir_creates_directory(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            entry = cap.mkdir("/tmp/mkdir_test")
            assert entry.name == "mkdir_test"
            assert entry.type == "directory"
            assert entry.path == "/tmp/mkdir_test"

    def test_mkdir_creates_parents(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            entry = cap.mkdir("/tmp/a/b/c/d")
            assert entry.type == "directory"

    def test_mkdir_already_exists(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/exist_test")
            entry = cap.mkdir("/tmp/exist_test")
            assert entry.type == "directory"


@requires_auth
class TestFilesystemRemove:
    def test_remove_file(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.upload("/tmp/rm_test.txt", b"delete me")
            entries_before = cap.list_dir("/tmp")
            assert any(e.name == "rm_test.txt" for e in entries_before)
            cap.remove("/tmp/rm_test.txt")
            entries_after = cap.list_dir("/tmp")
            assert not any(e.name == "rm_test.txt" for e in entries_after)

    def test_remove_directory(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/rm_dir_test")
            cap.upload("/tmp/rm_dir_test/file.txt", b"inside")
            cap.remove("/tmp/rm_dir_test")
            entries = cap.list_dir("/tmp")
            assert not any(e.name == "rm_dir_test" for e in entries)

    def test_upload_download_remove_roundtrip(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            content = b"round trip test data " * 100
            cap.upload("/tmp/rt.txt", content)
            downloaded = cap.download("/tmp/rt.txt")
            assert downloaded == content
            cap.remove("/tmp/rt.txt")
            with pytest.raises(Exception):
                cap.download("/tmp/rt.txt")


@requires_auth
class TestStreamUploadDownload:
    def test_stream_upload_and_download(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            chunks = [b"chunk0_", b"chunk1_", b"chunk2"]

            def data_gen():
                yield from chunks

            cap.stream_upload("/tmp/stream_test.bin", data_gen())
            downloaded = cap.download("/tmp/stream_test.bin")
            assert downloaded == b"chunk0_chunk1_chunk2"

    def test_stream_download_large(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            content = b"x" * 65536 * 3
            cap.upload("/tmp/large.bin", content)
            collected = b""
            for chunk in cap.stream_download("/tmp/large.bin"):
                collected += chunk
            assert collected == content


@requires_auth
class TestPty:
    def test_pty_basic_output(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/sh", cwd="/tmp") as term:
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
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/sh") as term:
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
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/echo", args=["immediate"]) as term:
                events = list(term)
                types = [e.type for e in events]
                assert PtyEventType.started in types
                assert PtyEventType.output in types or PtyEventType.exit in types

    def test_pty_resize(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/sh", cols=80, rows=24) as term:
                for event in term:
                    if event.type == PtyEventType.started:
                        term.resize(120, 40)
                        term.write(b"exit\n")
                    elif event.type == PtyEventType.exit:
                        break

    def test_pty_envs(self, client):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/sh", envs={"MY_VAR": "hello_env"}) as term:
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
            cap = await async_client.capsules.create(
                template="minimal", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)
                await cap.async_mkdir("/tmp/async_ls_test")
                await cap.async_upload("/tmp/async_ls_test/file.txt", b"data")
                entries = await cap.async_list_dir("/tmp/async_ls_test")
                assert isinstance(entries, list)
                assert any(e.name == "file.txt" for e in entries)
            finally:
                await cap.async_destroy()

    @pytest.mark.asyncio
    async def test_async_mkdir(self, async_client):
        async with async_client:
            cap = await async_client.capsules.create(
                template="minimal", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)
                entry = await cap.async_mkdir("/tmp/async_mkdir_test")
                assert entry.type == "directory"
                assert entry.name == "async_mkdir_test"
            finally:
                await cap.async_destroy()

    @pytest.mark.asyncio
    async def test_async_remove(self, async_client):
        async with async_client:
            cap = await async_client.capsules.create(
                template="minimal", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)
                await cap.async_upload("/tmp/async_rm.txt", b"bye")
                entries = await cap.async_list_dir("/tmp")
                assert any(e.name == "async_rm.txt" for e in entries)
                await cap.async_remove("/tmp/async_rm.txt")
                entries = await cap.async_list_dir("/tmp")
                assert not any(e.name == "async_rm.txt" for e in entries)
            finally:
                await cap.async_destroy()

    @pytest.mark.asyncio
    async def test_async_full_filesystem_roundtrip(self, async_client):
        async with async_client:
            cap = await async_client.capsules.create(
                template="minimal", timeout_sec=120
            )
            try:
                await cap.async_wait_ready(timeout=60, interval=1)

                await cap.async_mkdir("/tmp/async_rt")
                await cap.async_upload("/tmp/async_rt/file.txt", b"async content")
                entries = await cap.async_list_dir("/tmp/async_rt")
                assert any(e.name == "file.txt" for e in entries)

                data = await cap.async_download("/tmp/async_rt/file.txt")
                assert data == b"async content"

                await cap.async_remove("/tmp/async_rt/file.txt")
                entries = await cap.async_list_dir("/tmp/async_rt")
                assert not any(e.name == "file.txt" for e in entries)
            finally:
                await cap.async_destroy()
