from __future__ import annotations

import pytest

from wrenn import Capsule
from wrenn.models import FileEntry

pytestmark = pytest.mark.integration


class TestFiles:
    """Shared capsule for filesystem tests."""

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        cls.capsule = Capsule(wait=True)

    @classmethod
    def teardown_class(cls):
        try:
            cls.capsule.destroy()
        except Exception:
            pass

    def test_write_and_read(self):
        self.capsule.files.write("/tmp/test.txt", "hello world")
        content = self.capsule.files.read("/tmp/test.txt")
        assert content == "hello world"

    def test_write_and_read_bytes(self):
        data = b"\x00\x01\x02\xff"
        self.capsule.files.write("/tmp/test.bin", data)
        result = self.capsule.files.read_bytes("/tmp/test.bin")
        assert result == data

    def test_list_directory(self):
        self.capsule.files.write("/tmp/listdir/a.txt", "a")
        self.capsule.files.write("/tmp/listdir/b.txt", "b")
        entries = self.capsule.files.list("/tmp/listdir")
        assert isinstance(entries, list)
        names = [e.name for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_exists(self):
        self.capsule.files.write("/tmp/exists_test.txt", "x")
        assert self.capsule.files.exists("/tmp/exists_test.txt")
        assert not self.capsule.files.exists("/tmp/does_not_exist_xyz.txt")

    def test_make_dir(self):
        entry = self.capsule.files.make_dir("/tmp/newdir")
        assert isinstance(entry, FileEntry)
        assert self.capsule.files.exists("/tmp/newdir")

    def test_make_dir_idempotent(self):
        self.capsule.files.make_dir("/tmp/idempotent_dir")
        entry = self.capsule.files.make_dir("/tmp/idempotent_dir")
        assert isinstance(entry, FileEntry)

    def test_remove_file(self):
        self.capsule.files.write("/tmp/to_remove.txt", "delete me")
        assert self.capsule.files.exists("/tmp/to_remove.txt")
        self.capsule.files.remove("/tmp/to_remove.txt")
        assert not self.capsule.files.exists("/tmp/to_remove.txt")

    def test_remove_directory(self):
        self.capsule.files.make_dir("/tmp/dir_to_remove")
        self.capsule.files.write("/tmp/dir_to_remove/child.txt", "data")
        self.capsule.files.remove("/tmp/dir_to_remove")
        assert not self.capsule.files.exists("/tmp/dir_to_remove")

    def test_write_creates_parent_dirs(self):
        self.capsule.files.write("/tmp/deep/nested/dir/file.txt", "nested")
        content = self.capsule.files.read("/tmp/deep/nested/dir/file.txt")
        assert content == "nested"

    def test_list_with_depth(self):
        self.capsule.files.write("/tmp/depth_test/a/b.txt", "deep")
        entries_shallow = self.capsule.files.list("/tmp/depth_test", depth=1)
        entries_deep = self.capsule.files.list("/tmp/depth_test", depth=2)
        assert len(entries_deep) >= len(entries_shallow)

    def test_overwrite_file(self):
        self.capsule.files.write("/tmp/overwrite.txt", "original")
        self.capsule.files.write("/tmp/overwrite.txt", "updated")
        content = self.capsule.files.read("/tmp/overwrite.txt")
        assert content == "updated"

    def test_upload_and_download_stream(self):
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        self.capsule.files.upload_stream("/tmp/streamed.bin", iter(chunks))
        downloaded = b"".join(self.capsule.files.download_stream("/tmp/streamed.bin"))
        assert downloaded == b"chunk1chunk2chunk3"
