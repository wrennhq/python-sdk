from __future__ import annotations

from wrenn.client import WrennClient
from wrenn.pty import PtyEventType

from .conftest import requires_auth


@requires_auth
class TestPty:
    def test_pty_basic_output(self, client: WrennClient):
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

    def test_pty_tag_and_pid(self, client: WrennClient):
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

    def test_pty_exit_on_command_exit(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/echo", args=["immediate"]) as term:
                events = list(term)
                types = [e.type for e in events]
                assert PtyEventType.started in types
                assert PtyEventType.output in types or PtyEventType.exit in types

    def test_pty_resize(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            with cap.pty(cmd="/bin/sh", cols=80, rows=24) as term:
                for event in term:
                    if event.type == PtyEventType.started:
                        term.resize(120, 40)
                        term.write(b"exit\n")
                    elif event.type == PtyEventType.exit:
                        break

    def test_pty_envs(self, client: WrennClient):
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
