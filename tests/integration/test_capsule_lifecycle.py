from __future__ import annotations

import pytest

from wrenn.capsule import Capsule
from wrenn.client import WrennClient
from wrenn.exceptions import WrennNotFoundError, WrennValidationError

from .conftest import requires_auth


@requires_auth
class TestCapsuleLifecycle:
    def test_create_exec_destroy(self, minimal_capsule: Capsule):
        result = minimal_capsule.exec("echo", args=["hello"])
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_exec_with_args(self, minimal_capsule: Capsule):
        result = minimal_capsule.exec("echo", args=["hello", "world"])
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    def test_exec_nonzero_exit(self, minimal_capsule: Capsule):
        result = minimal_capsule.exec("sh", args=["-c", "exit 42"])
        assert result.exit_code == 42

    def test_exec_stderr(self, minimal_capsule: Capsule):
        result = minimal_capsule.exec("sh", args=["-c", "echo err>&2"])
        assert result.exit_code == 0
        assert "err" in result.stderr

    def test_context_manager_cleanup(self, client: WrennClient):
        # This test explicitly requires manual management to verify the context manager
        cap = client.capsules.create(template="minimal", timeout_sec=120)
        cap_id = cap.id

        with cap:
            cap.wait_ready(timeout=60, interval=1)

        fetched = client.capsules.get(cap_id)
        assert fetched.status in ("stopped", "destroyed")


@requires_auth
class TestPauseResume:
    def test_pause_and_resume(self, minimal_capsule: Capsule):
        minimal_capsule.pause()
        assert minimal_capsule.status == "paused"

        minimal_capsule.resume()
        minimal_capsule.wait_ready(timeout=60, interval=1)

        result = minimal_capsule.exec("echo", args=["resumed"])
        assert result.exit_code == 0
        assert "resumed" in result.stdout


@requires_auth
class TestPing:
    def test_ping_resets_timer(self, minimal_capsule: Capsule):
        minimal_capsule.ping()
        result = minimal_capsule.exec("echo", args=["still_alive"])
        assert result.exit_code == 0
        assert "still_alive" in result.stdout


@requires_auth
class TestProxy:
    def test_get_url(self, minimal_capsule: Capsule):
        url = minimal_capsule.get_url(8888)
        assert minimal_capsule.id in url
        assert "8888" in url


@requires_auth
class TestListAndGet:
    def test_list_capsules(self, client: WrennClient, minimal_capsule: Capsule):
        # Require minimal_capsule to ensure one exists, use client to list
        boxes = client.capsules.list()
        ids = [b.id for b in boxes]
        assert minimal_capsule.id in ids

    def test_get_existing_capsule(self, client: WrennClient, minimal_capsule: Capsule):
        fetched = client.capsules.get(minimal_capsule.id)
        assert fetched.id == minimal_capsule.id
        assert fetched.status == "running"

    def test_get_nonexistent_capsule(self, client: WrennClient):
        with pytest.raises((WrennNotFoundError, WrennValidationError)):
            client.capsules.get("cl-nonexistent00000000000000000")
