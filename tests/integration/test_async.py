from __future__ import annotations

import pytest

from wrenn.capsule import Capsule

from .conftest import requires_auth

# --- Tests ---


@requires_auth
class TestAsyncCapsuleLifecycle:
    @pytest.mark.asyncio
    async def test_async_create_exec_destroy(self, async_minimal_capsule: Capsule):
        result = await async_minimal_capsule.async_exec("echo", args=["async_hello"])
        assert result.exit_code == 0
        assert "async_hello" in result.stdout

    @pytest.mark.asyncio
    async def test_async_upload_download(self, async_minimal_capsule: Capsule):
        content = b"Async upload test"
        await async_minimal_capsule.async_upload("/tmp/async_test.txt", content)
        downloaded = await async_minimal_capsule.async_download("/tmp/async_test.txt")
        assert downloaded == content

    @pytest.mark.asyncio
    async def test_async_run_code(self, async_python_capsule: Capsule):
        r = await async_python_capsule.async_run_code("42 * 2")
        assert r.text == "84"


@requires_auth
class TestAsyncFilesystem:
    @pytest.mark.asyncio
    async def test_async_list_dir(self, async_minimal_capsule: Capsule):
        await async_minimal_capsule.async_mkdir("/tmp/async_ls_test")
        await async_minimal_capsule.async_upload("/tmp/async_ls_test/file.txt", b"data")
        entries = await async_minimal_capsule.async_list_dir("/tmp/async_ls_test")

        assert isinstance(entries, list)
        assert any(e.name == "file.txt" for e in entries)

    @pytest.mark.asyncio
    async def test_async_mkdir(self, async_minimal_capsule: Capsule):
        entry = await async_minimal_capsule.async_mkdir("/tmp/async_mkdir_test")
        assert entry.type == "directory"
        assert entry.name == "async_mkdir_test"

    @pytest.mark.asyncio
    async def test_async_remove(self, async_minimal_capsule: Capsule):
        await async_minimal_capsule.async_upload("/tmp/async_rm.txt", b"bye")

        entries = await async_minimal_capsule.async_list_dir("/tmp")
        assert any(e.name == "async_rm.txt" for e in entries)

        await async_minimal_capsule.async_remove("/tmp/async_rm.txt")
        entries = await async_minimal_capsule.async_list_dir("/tmp")
        assert not any(e.name == "async_rm.txt" for e in entries)

    @pytest.mark.asyncio
    async def test_async_full_filesystem_roundtrip(
        self, async_minimal_capsule: Capsule
    ):
        await async_minimal_capsule.async_mkdir("/tmp/async_rt")
        await async_minimal_capsule.async_upload(
            "/tmp/async_rt/file.txt", b"async content"
        )

        entries = await async_minimal_capsule.async_list_dir("/tmp/async_rt")
        assert any(e.name == "file.txt" for e in entries)

        data = await async_minimal_capsule.async_download("/tmp/async_rt/file.txt")
        assert data == b"async content"

        await async_minimal_capsule.async_remove("/tmp/async_rt/file.txt")
        entries = await async_minimal_capsule.async_list_dir("/tmp/async_rt")
        assert not any(e.name == "file.txt" for e in entries)
