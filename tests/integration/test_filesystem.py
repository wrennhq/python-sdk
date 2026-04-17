from __future__ import annotations

import pytest

from wrenn.client import WrennClient

from .conftest import requires_auth


@requires_auth
class TestFileIO:
    def test_upload_and_download(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            content = b"Hello from integration test!"
            cap.upload("/tmp/test_file.txt", content)
            downloaded = cap.download("/tmp/test_file.txt")
            assert downloaded == content

    def test_download_nonexistent_file(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with pytest.raises(Exception):
                cap.download("/tmp/no_such_file_12345")


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

    def test_list_dir_after_mkdir(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/fs_test_dir")
            entries = cap.list_dir("/tmp")
            names = [e.name for e in entries]
            assert "fs_test_dir" in names

    def test_list_dir_file_metadata(self, client: WrennClient):
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

    def test_list_dir_depth(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/depth_a/depth_b")
            cap.upload("/tmp/depth_a/depth_b/nested.txt", b"deep")
            entries = cap.list_dir("/tmp/depth_a", depth=2)
            paths = [e.path for e in entries]
            assert any("nested.txt" in p for p in paths)

    def test_list_dir_empty_directory(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/empty_dir_test")
            entries = cap.list_dir("/tmp/empty_dir_test")
            assert entries == []


@requires_auth
class TestFilesystemMkdir:
    def test_mkdir_creates_directory(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            entry = cap.mkdir("/tmp/mkdir_test")
            assert entry.name == "mkdir_test"
            assert entry.type == "directory"
            assert entry.path == "/tmp/mkdir_test"

    def test_mkdir_creates_parents(self, client: WrennClient):
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
    def test_remove_file(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.upload("/tmp/rm_test.txt", b"delete me")
            entries_before = cap.list_dir("/tmp")
            assert any(e.name == "rm_test.txt" for e in entries_before)
            cap.remove("/tmp/rm_test.txt")
            entries_after = cap.list_dir("/tmp")
            assert not any(e.name == "rm_test.txt" for e in entries_after)

    def test_remove_directory(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            cap.mkdir("/tmp/rm_dir_test")
            cap.upload("/tmp/rm_dir_test/file.txt", b"inside")
            cap.remove("/tmp/rm_dir_test")
            entries = cap.list_dir("/tmp")
            assert not any(e.name == "rm_dir_test" for e in entries)

    def test_upload_download_remove_roundtrip(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            content = b"round trip test data " * 100
            cap.upload("/tmp/rt.txt", content)
            downloaded = cap.download("/tmp/rt.txt")
            assert downloaded == content
            cap.remove("/tmp/rt.txt")
            with pytest.raises(Exception):
                cap.download("/tmp/rt.txt")
