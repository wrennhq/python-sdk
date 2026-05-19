"""Advanced integration tests against a live Wrenn server.

Skipped automatically when ``WRENN_API_KEY`` is not set (see conftest.py).

Covers working-directory / environment handling, long-running commands
(``apt-get``), interactive PTY sessions, streaming exec, and real ``git``
workflows including cloning ``github.com/wrennhq/wrenn``.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from wrenn import Capsule
from wrenn.commands import StreamExitEvent, StreamStartEvent
from wrenn.exceptions import WrennError
from wrenn.pty import PtyEventType

pytestmark = pytest.mark.integration

WRENN_REPO = "https://github.com/wrennhq/wrenn"

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


# ══════════════════════════════════════════════════════════════════
# Working directory & environment
# ══════════════════════════════════════════════════════════════════


class TestCommandEnvironment:
    """cwd / envs handling for foreground commands."""

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

    def test_cwd_changes_working_directory(self):
        result = self.capsule.commands.run("pwd", cwd="/tmp")
        assert result.exit_code == 0
        assert result.stdout.strip() == "/tmp"

    def test_default_cwd_is_home(self):
        result = self.capsule.commands.run("pwd")
        assert result.stdout.strip() == "/root"

    def test_cwd_resolves_relative_paths(self):
        self.capsule.files.make_dir("/tmp/cwd_probe/sub")
        result = self.capsule.commands.run("ls", cwd="/tmp/cwd_probe")
        assert "sub" in result.stdout

    def test_cwd_nonexistent_raises(self):
        with pytest.raises(WrennError):
            self.capsule.commands.run("pwd", cwd="/no/such/dir/xyz")

    def test_cwd_does_not_persist_between_calls(self):
        # Each run is a fresh process — `cd` in one does not affect the next.
        self.capsule.commands.run("cd /tmp")
        result = self.capsule.commands.run("pwd")
        assert result.stdout.strip() == "/root"

    def test_single_env_var(self):
        result = self.capsule.commands.run("echo $GREETING", envs={"GREETING": "hi"})
        assert result.stdout.strip() == "hi"

    def test_multiple_env_vars(self):
        result = self.capsule.commands.run(
            "echo $A-$B-$C", envs={"A": "1", "B": "2", "C": "3"}
        )
        assert result.stdout.strip() == "1-2-3"

    def test_env_vars_do_not_leak_between_calls(self):
        self.capsule.commands.run("echo $SECRET", envs={"SECRET": "leaky"})
        result = self.capsule.commands.run("echo [$SECRET]")
        assert result.stdout.strip() == "[]"

    def test_env_var_with_special_chars(self):
        value = "a b&c|d;e"
        result = self.capsule.commands.run('printf "%s" "$X"', envs={"X": value})
        assert result.stdout == value

    def test_base_environment_present(self):
        result = self.capsule.commands.run("echo $HOME; echo $PATH")
        lines = result.stdout.strip().splitlines()
        assert lines[0] == "/root"
        assert "/usr/bin" in lines[1]


# ══════════════════════════════════════════════════════════════════
# Long-running commands
# ══════════════════════════════════════════════════════════════════


class TestLongRunningCommands:
    """apt-get installs and other slow commands."""

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

    def test_apt_get_install(self):
        result = self.capsule.commands.run(
            "apt-get update -qq && apt-get install -y -qq cowsay", timeout=300
        )
        assert result.exit_code == 0

    def test_apt_installed_binary_runs(self):
        # Depends on test_apt_get_install having installed the package.
        self.capsule.commands.run("apt-get install -y -qq cowsay", timeout=300)
        result = self.capsule.commands.run("/usr/games/cowsay moo")
        assert result.exit_code == 0
        assert "moo" in result.stdout

    def test_foreground_timeout_raises(self):
        # A command exceeding its timeout surfaces as a server-side error.
        with pytest.raises(WrennError):
            self.capsule.commands.run("sleep 20", timeout=2)

    def test_long_sleep_in_background_returns_immediately(self):
        start = time.monotonic()
        handle = self.capsule.commands.run(
            "sleep 60", background=True, tag="long-sleep"
        )
        elapsed = time.monotonic() - start
        assert elapsed < 10
        assert handle.pid > 0
        self.capsule.commands.kill(handle.pid)

    def test_slow_command_within_timeout(self):
        result = self.capsule.commands.run("sleep 3 && echo done", timeout=30)
        assert result.exit_code == 0
        assert result.stdout.strip() == "done"


# ══════════════════════════════════════════════════════════════════
# PTY sessions
# ══════════════════════════════════════════════════════════════════


def _drain_pty(term, *, max_events: int = 200) -> tuple[bytes, int | None]:
    """Collect PTY output until exit; return (output, exit_code)."""
    output = b""
    exit_code: int | None = None
    for i, event in enumerate(term):
        if event.type == PtyEventType.output and event.data:
            output += event.data
        elif event.type == PtyEventType.exit:
            exit_code = event.exit_code
            break
        elif event.type == PtyEventType.error and event.fatal:
            break
        if i >= max_events:
            break
    return output, exit_code


class TestPty:
    """Interactive PTY behaviour."""

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

    def test_pty_runs_command_and_exits(self):
        with self.capsule.pty(cmd="/bin/bash") as term:
            term.write(b"echo pty-result-$((6*7))\n")
            term.write(b"exit\n")
            output, exit_code = _drain_pty(term)
        assert b"pty-result-42" in output
        assert exit_code is not None

    def test_pty_started_event_sets_tag_and_pid(self):
        with self.capsule.pty(cmd="/bin/bash") as term:
            term.write(b"exit\n")
            _drain_pty(term)
            assert term.tag is not None
            assert term.tag.startswith("pty-")
            assert term.pid is not None and term.pid > 0

    def test_pty_respects_cwd(self):
        with self.capsule.pty(cmd="/bin/bash", cwd="/tmp") as term:
            term.write(b"pwd\n")
            term.write(b"exit\n")
            output, _ = _drain_pty(term)
        assert b"/tmp" in output

    def test_pty_respects_envs(self):
        with self.capsule.pty(cmd="/bin/bash", envs={"PTY_VAR": "xyzzy"}) as term:
            term.write(b"echo marker-$PTY_VAR\n")
            term.write(b"exit\n")
            output, _ = _drain_pty(term)
        assert b"marker-xyzzy" in output

    def test_pty_resize(self):
        with self.capsule.pty(cmd="/bin/bash", cols=80, rows=24) as term:
            term.resize(120, 40)
            term.write(b"echo resized\n")
            term.write(b"exit\n")
            output, _ = _drain_pty(term)
        assert b"resized" in output

    def test_pty_explicit_command(self):
        with self.capsule.pty(cmd="/bin/echo", args=["hello-from-argv"]) as term:
            output, exit_code = _drain_pty(term)
        assert b"hello-from-argv" in output

    def test_pty_exit_code_nonzero(self):
        with self.capsule.pty(cmd="/bin/bash") as term:
            term.write(b"exit 3\n")
            _, exit_code = _drain_pty(term)
        assert exit_code == 3

    def test_pty_survives_idle_ping_cycle(self):
        # The server emits a keepalive `ping` (~every 30s); the SDK must
        # auto-reply `pong` and the session must stay usable afterwards.
        with self.capsule.pty(cmd="/bin/bash") as term:
            saw_ping = False
            for event in term:
                if event.type == PtyEventType.ping:
                    saw_ping = True
                    break
                if event.type == PtyEventType.exit:
                    break
                if event.type == PtyEventType.error and event.fatal:
                    break
            assert saw_ping, "no keepalive ping received"
            term.write(b"echo still-alive\n")
            term.write(b"exit\n")
            output, _ = _drain_pty(term)
        assert b"still-alive" in output


# ══════════════════════════════════════════════════════════════════
# Streaming exec
# ══════════════════════════════════════════════════════════════════


class TestStreamingExec:
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

    def test_stream_emits_start_and_exit(self):
        events = list(self.capsule.commands.stream("echo streamed"))
        types = [e.type for e in events]
        assert "exit" in types
        starts = [e for e in events if isinstance(e, StreamStartEvent)]
        exits = [e for e in events if isinstance(e, StreamExitEvent)]
        assert exits and exits[0].exit_code == 0
        if starts:
            assert starts[0].pid > 0

    def test_stream_captures_stdout(self):
        events = list(self.capsule.commands.stream("for i in 1 2 3; do echo n$i; done"))
        out = "".join(
            e.data for e in events if e.type == "stdout" and getattr(e, "data", None)
        )
        assert "n1" in out and "n3" in out

    def test_stream_nonzero_exit(self):
        events = list(self.capsule.commands.stream("exit 5"))
        exits = [e for e in events if isinstance(e, StreamExitEvent)]
        assert exits and exits[0].exit_code == 5


# ══════════════════════════════════════════════════════════════════
# Process connect — attach to a background process over WebSocket
# ══════════════════════════════════════════════════════════════════


class TestProcessConnect:
    """commands.connect — must survive the server's abrupt WebSocket close."""

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

    def test_connect_streams_running_process(self):
        handle = self.capsule.commands.run(
            "for i in $(seq 1 5); do echo tick$i; sleep 1; done",
            background=True,
            tag="connect-run",
        )
        time.sleep(0.3)
        events = list(self.capsule.commands.connect(handle.pid))
        types = [e.type for e in events]
        assert "exit" in types
        # connect streams output from the attach point onward, so early
        # ticks may be missed — assert it captured the live tail.
        out = "".join(
            e.data for e in events if e.type == "stdout" and getattr(e, "data", None)
        )
        assert "tick" in out

    def test_connect_to_finished_process_does_not_raise(self):
        handle = self.capsule.commands.run("echo quick", background=True)
        time.sleep(2)
        # Process already exited — server closes the WebSocket abruptly;
        # the iterator must terminate cleanly rather than raise.
        events = list(self.capsule.commands.connect(handle.pid))
        assert isinstance(events, list)


# ══════════════════════════════════════════════════════════════════
# Git — real workflows including cloning wrennhq/wrenn
# ══════════════════════════════════════════════════════════════════


class TestGitClone:
    """Clone github.com/wrennhq/wrenn and operate on it."""

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        _ensure_env()
        cls.capsule = Capsule(wait=True)
        cls.capsule.git.clone(WRENN_REPO, "/root/wrenn", depth=1, timeout=300)

    @classmethod
    def teardown_class(cls):
        try:
            cls.capsule.destroy()
        except Exception:
            pass

    def test_clone_created_repo(self):
        assert self.capsule.files.exists("/root/wrenn/.git")

    def test_clone_checked_out_files(self):
        entries = self.capsule.files.list("/root/wrenn")
        names = [e.name for e in entries]
        assert "README.md" in names

    def test_status_of_clone_is_clean(self):
        status = self.capsule.git.status(cwd="/root/wrenn")
        assert status.branch == "main"
        assert status.is_clean

    def test_branches_lists_main(self):
        branches = self.capsule.git.branches(cwd="/root/wrenn")
        names = [b.name for b in branches]
        assert "main" in names
        assert any(b.is_current for b in branches)

    def test_remote_get_origin(self):
        url = self.capsule.git.remote_get("origin", cwd="/root/wrenn")
        assert url is not None
        assert "wrennhq/wrenn" in url

    def test_git_log_has_commit(self):
        result = self.capsule.commands.run("git log --oneline -1", cwd="/root/wrenn")
        assert result.exit_code == 0
        assert result.stdout.strip()

    def test_modify_add_commit(self):
        marker = uuid.uuid4().hex
        self.capsule.git.configure_user(
            "CI Bot", "ci@example.com", cwd="/root/wrenn", scope="local"
        )
        self.capsule.files.write(f"/root/wrenn/sdk_probe_{marker}.txt", marker)
        self.capsule.git.add([f"sdk_probe_{marker}.txt"], cwd="/root/wrenn")

        staged = self.capsule.git.status(cwd="/root/wrenn")
        assert staged.has_staged

        result = self.capsule.git.commit("probe commit", cwd="/root/wrenn")
        assert result.exit_code == 0

        after = self.capsule.git.status(cwd="/root/wrenn")
        assert after.is_clean
        assert after.ahead >= 1

    def test_create_and_checkout_branch_in_clone(self):
        self.capsule.git.create_branch("sdk-feature", cwd="/root/wrenn")
        branches = self.capsule.git.branches(cwd="/root/wrenn")
        current = [b for b in branches if b.is_current]
        assert current and current[0].name == "sdk-feature"
        self.capsule.git.checkout_branch("main", cwd="/root/wrenn")

    def test_diff_via_commands(self):
        self.capsule.files.write("/root/wrenn/README.md", "overwritten\n")
        try:
            result = self.capsule.commands.run("git diff --stat", cwd="/root/wrenn")
            assert "README.md" in result.stdout
        finally:
            self.capsule.git.restore(["README.md"], worktree=True, cwd="/root/wrenn")


class TestGitErrors:
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

    def test_clone_nonexistent_repo_raises(self):
        from wrenn._git import GitError

        with pytest.raises(GitError):
            self.capsule.git.clone(
                "https://github.com/wrennhq/this-repo-does-not-exist-xyz",
                "/root/missing",
                timeout=120,
            )

    def test_status_outside_repo_raises(self):
        from wrenn._git import GitError

        with pytest.raises(GitError):
            self.capsule.git.status(cwd="/tmp")

    def test_clone_with_branch(self):
        self.capsule.git.clone(
            WRENN_REPO, "/root/wrenn-main", branch="main", depth=1, timeout=300
        )
        status = self.capsule.git.status(cwd="/root/wrenn-main")
        assert status.branch == "main"
