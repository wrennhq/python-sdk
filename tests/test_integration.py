from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from wrenn import Capsule, CommandResult
from wrenn.commands import CommandHandle, ProcessInfo
from wrenn.models import Capsule as CapsuleModel, FileEntry, Status

pytestmark = pytest.mark.integration

_env_loaded = False


def _ensure_env() -> None:
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


class TestCapsuleLifecycle:
    """Each test manages its own capsule to test create/destroy paths."""

    def setup_method(self):
        _ensure_env()

    def test_create_and_destroy(self):
        capsule = Capsule()
        capsule_id = capsule.capsule_id
        try:
            assert capsule_id
            assert capsule.info is not None
        finally:
            capsule.destroy()

        info = Capsule.get_info(capsule_id)
        assert info.status in (Status.stopped, Status.missing)

    def test_create_with_wait(self):
        capsule = Capsule(wait=True)
        try:
            assert capsule.info is not None
            assert capsule.info.status == Status.running
        finally:
            capsule.destroy()

    def test_context_manager_destroys(self):
        with Capsule(wait=True) as capsule:
            capsule_id = capsule.capsule_id
            assert capsule.is_running()

        info = Capsule.get_info(capsule_id)
        assert info.status in (Status.stopped, Status.missing)

    def test_get_info(self):
        capsule = Capsule(wait=True)
        try:
            info = capsule.get_info()
            assert isinstance(info, CapsuleModel)
            assert info.id == capsule.capsule_id
            assert info.status == Status.running
        finally:
            capsule.destroy()

    def test_pause_and_resume(self):
        capsule = Capsule(wait=True)
        try:
            paused = capsule.pause()
            assert paused.status == Status.paused
            assert not capsule.is_running()

            resumed = capsule.resume()
            assert resumed.status == Status.running
        finally:
            capsule.destroy()

    def test_static_destroy(self):
        capsule = Capsule(wait=True)
        capsule_id = capsule.capsule_id
        try:
            Capsule.destroy(capsule_id)
        except Exception:
            capsule.destroy()
            raise

        info = Capsule.get_info(capsule_id)
        assert info.status in (Status.stopped, Status.missing)

    def test_connect_to_existing(self):
        capsule = Capsule(wait=True)
        try:
            connected = Capsule.connect(capsule.capsule_id)
            assert connected.capsule_id == capsule.capsule_id
            assert connected.info is not None
            assert connected.info.status == Status.running
        finally:
            capsule.destroy()

    def test_connect_resumes_paused(self):
        capsule = Capsule(wait=True)
        try:
            capsule.pause()
            connected = Capsule.connect(capsule.capsule_id)
            assert connected.info is not None
            assert connected.info.status == Status.running
        finally:
            capsule.destroy()

    def test_list_capsules(self):
        capsule = Capsule(wait=True)
        try:
            capsules = Capsule.list()
            assert isinstance(capsules, list)
            ids = [c.id for c in capsules]
            assert capsule.capsule_id in ids
        finally:
            capsule.destroy()

    def test_wait_ready(self):
        capsule = Capsule()
        try:
            capsule.wait_ready(timeout=60)
            assert capsule.is_running()
        finally:
            capsule.destroy()

    def test_ping(self):
        capsule = Capsule(wait=True)
        try:
            capsule.ping()
        finally:
            capsule.destroy()


class TestCommands:
    """Shared capsule for command execution tests."""

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        _ensure_env()
        cls.capsule = Capsule(wait=True)

    @classmethod
    def teardown_class(cls):
        try:
            cls.capsule.destroy()
        except Exception:
            pass

    def test_run_foreground(self):
        result = self.capsule.commands.run("echo hello")
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_run_stderr(self):
        result = self.capsule.commands.run("echo error >&2")
        assert "error" in result.stderr

    def test_run_exit_code(self):
        result = self.capsule.commands.run("exit 42")
        assert result.exit_code == 42

    def test_run_with_envs(self):
        result = self.capsule.commands.run(
            "export MY_VAR=test_value && echo $MY_VAR"
        )
        assert "test_value" in result.stdout

    def test_run_with_cwd(self):
        result = self.capsule.commands.run("cd /tmp && pwd")
        assert result.stdout.strip() == "/tmp"

    def test_run_multiline_output(self):
        result = self.capsule.commands.run("echo -e 'line1\\nline2\\nline3'")
        assert result.exit_code == 0
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 3

    def test_run_background(self):
        handle = self.capsule.commands.run(
            "sleep 30", background=True, tag="bg-test"
        )
        assert isinstance(handle, CommandHandle)
        assert handle.pid > 0
        assert handle.tag == "bg-test"
        assert handle.capsule_id == self.capsule.capsule_id

        self.capsule.commands.kill(handle.pid)

    def test_list_processes(self):
        handle = self.capsule.commands.run(
            "sleep 30", background=True, tag="list-test"
        )
        try:
            time.sleep(0.5)
            processes = self.capsule.commands.list()
            assert isinstance(processes, list)
            pids = [p.pid for p in processes]
            assert handle.pid in pids

            proc = next(p for p in processes if p.pid == handle.pid)
            assert isinstance(proc, ProcessInfo)
        finally:
            self.capsule.commands.kill(handle.pid)

    def test_kill_process(self):
        handle = self.capsule.commands.run(
            "sleep 30", background=True
        )
        self.capsule.commands.kill(handle.pid)
        time.sleep(0.5)

        processes = self.capsule.commands.list()
        pids = [p.pid for p in processes]
        assert handle.pid not in pids

    def test_run_duration_ms(self):
        result = self.capsule.commands.run("sleep 1")
        assert result.duration_ms is None or result.duration_ms >= 900


class TestFiles:
    """Shared capsule for filesystem tests."""

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        _ensure_env()
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


class TestGit:
    """Shared capsule for git operation tests.

    Initializes a repo at /root (default cwd) since the exec API
    does not support the cwd parameter.
    """

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        _ensure_env()
        cls.capsule = Capsule(wait=True)
        cls.capsule.git.init(".", initial_branch="main")
        cls.capsule.git.configure_user("Test User", "test@example.com")

    @classmethod
    def teardown_class(cls):
        try:
            cls.capsule.destroy()
        except Exception:
            pass

    def test_init_created_repo(self):
        assert self.capsule.files.exists("/root/.git")

    def test_status_clean(self):
        status = self.capsule.git.status()
        assert status.branch == "main"

    def test_add_and_commit(self):
        self.capsule.files.write("/root/hello.txt", "hello git")
        self.capsule.git.add(all=True)
        result = self.capsule.git.commit("initial commit")
        assert result.exit_code == 0

    def test_status_after_commit(self):
        status = self.capsule.git.status()
        assert status.is_clean

    def test_status_with_changes(self):
        self.capsule.files.write("/root/dirty.txt", "uncommitted")
        try:
            status = self.capsule.git.status()
            assert not status.is_clean
            paths = [f.path for f in status.files]
            assert "dirty.txt" in paths
        finally:
            self.capsule.files.remove("/root/dirty.txt")

    def test_branches(self):
        branches = self.capsule.git.branches()
        assert len(branches) >= 1
        names = [b.name for b in branches]
        assert "main" in names
        current = [b for b in branches if b.is_current]
        assert len(current) == 1

    def test_create_and_checkout_branch(self):
        self.capsule.git.create_branch("feature-1")
        branches = self.capsule.git.branches()
        names = [b.name for b in branches]
        assert "feature-1" in names

        current = [b for b in branches if b.is_current]
        assert current[0].name == "feature-1"

        self.capsule.git.checkout_branch("main")

    def test_delete_branch(self):
        self.capsule.git.create_branch("to-delete")
        self.capsule.git.checkout_branch("main")
        self.capsule.git.delete_branch("to-delete")

        branches = self.capsule.git.branches()
        names = [b.name for b in branches]
        assert "to-delete" not in names

    def test_set_and_get_config(self):
        self.capsule.git.set_config("test.key", "test-value")
        value = self.capsule.git.get_config("test.key")
        assert value == "test-value"

    def test_get_config_missing_returns_none(self):
        value = self.capsule.git.get_config("nonexistent.key")
        assert value is None
