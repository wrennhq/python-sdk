from __future__ import annotations

import pytest

from wrenn import Capsule

pytestmark = pytest.mark.integration


class TestGit:
    """Shared capsule for git operation tests.

    Initializes a repo at /root (default cwd) since the exec API
    does not support the cwd parameter.
    """

    capsule: Capsule

    @classmethod
    def setup_class(cls):
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
