from __future__ import annotations

import time

import pytest

from wrenn import Capsule, CommandResult
from wrenn.commands import CommandHandle, ProcessInfo

pytestmark = pytest.mark.integration


class TestCommands:
    """Shared capsule for command execution tests."""

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
        result = self.capsule.commands.run("export MY_VAR=test_value && echo $MY_VAR")
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
        handle = self.capsule.commands.run("sleep 30", background=True, tag="bg-test")
        assert isinstance(handle, CommandHandle)
        assert handle.pid > 0
        assert handle.tag == "bg-test"
        assert handle.capsule_id == self.capsule.capsule_id

        self.capsule.commands.kill(handle.pid)

    def test_list_processes(self):
        handle = self.capsule.commands.run("sleep 30", background=True, tag="list-test")
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
        handle = self.capsule.commands.run("sleep 30", background=True)
        self.capsule.commands.kill(handle.pid)
        time.sleep(0.5)

        processes = self.capsule.commands.list()
        pids = [p.pid for p in processes]
        assert handle.pid not in pids

    def test_run_duration_ms(self):
        result = self.capsule.commands.run("sleep 1")
        assert result.duration_ms is None or result.duration_ms >= 900
