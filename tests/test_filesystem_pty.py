from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import respx

from wrenn.capsule import Capsule
from wrenn.models import FileEntry
from wrenn.pty import (
    AsyncPtySession,
    PtyEventType,
    PtySession,
    _parse_pty_event,
)

BASE = "https://app.wrenn.dev/api"


def _make_capsule(cap_id: str = "cl-abc") -> Capsule:
    respx.post(f"{BASE}/v1/capsules").respond(
        201, json={"id": cap_id, "status": "running"}
    )
    return Capsule(api_key="wrn_test1234567890abcdef12345678")


class TestFilesRead:
    @respx.mock
    def test_read_returns_string(self):
        cap = _make_capsule()
        content = b"file contents here"
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/read").respond(
            200, content=content
        )
        data = cap.files.read("/app/main.py")
        assert data == "file contents here"

    @respx.mock
    def test_read_bytes(self):
        cap = _make_capsule()
        content = b"\x00\x01\x02"
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/read").respond(
            200, content=content
        )
        data = cap.files.read_bytes("/bin/binary")
        assert data == b"\x00\x01\x02"


class TestFilesWrite:
    @respx.mock
    def test_write_string(self):
        cap = _make_capsule()
        route = respx.post(f"{BASE}/v1/capsules/cl-abc/files/write").respond(204)
        cap.files.write("/app/main.py", "print('hello')")
        assert route.called

    @respx.mock
    def test_write_bytes(self):
        cap = _make_capsule()
        route = respx.post(f"{BASE}/v1/capsules/cl-abc/files/write").respond(204)
        cap.files.write("/app/data.bin", b"\x00\x01\x02")
        assert route.called


class TestFilesList:
    @respx.mock
    def test_list_returns_entries(self):
        cap = _make_capsule()
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/list").respond(
            200,
            json={
                "entries": [
                    {
                        "name": "main.py",
                        "path": "/home/user/main.py",
                        "type": "file",
                        "size": 1024,
                        "mode": 33188,
                        "permissions": "-rw-r--r--",
                        "owner": "root",
                        "group": "root",
                        "modified_at": 1712899200,
                        "symlink_target": None,
                    },
                    {
                        "name": "config",
                        "path": "/home/user/config",
                        "type": "directory",
                        "size": 4096,
                        "mode": 16877,
                        "permissions": "drwxr-xr-x",
                        "owner": "root",
                        "group": "root",
                        "modified_at": 1712899100,
                        "symlink_target": None,
                    },
                ]
            },
        )
        entries = cap.files.list("/home/user")
        assert len(entries) == 2
        assert isinstance(entries[0], FileEntry)
        assert entries[0].name == "main.py"
        assert entries[0].type == "file"
        assert entries[1].name == "config"
        assert entries[1].type == "directory"

    @respx.mock
    def test_list_with_depth(self):
        cap = _make_capsule()
        route = respx.post(f"{BASE}/v1/capsules/cl-abc/files/list").respond(
            200, json={"entries": []}
        )
        cap.files.list("/home/user", depth=3)
        body = json.loads(route.calls[0].request.content)
        assert body["depth"] == 3

    @respx.mock
    def test_list_empty(self):
        cap = _make_capsule()
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/list").respond(
            200, json={"entries": []}
        )
        entries = cap.files.list("/empty")
        assert entries == []


class TestFilesMakeDir:
    @respx.mock
    def test_make_dir_returns_entry(self):
        cap = _make_capsule()
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/mkdir").respond(
            200,
            json={
                "entry": {
                    "name": "data",
                    "path": "/home/user/data",
                    "type": "directory",
                    "size": 4096,
                    "mode": 16877,
                    "permissions": "drwxr-xr-x",
                    "owner": "root",
                    "group": "root",
                    "modified_at": 1712899200,
                    "symlink_target": None,
                }
            },
        )
        entry = cap.files.make_dir("/home/user/data")
        assert isinstance(entry, FileEntry)
        assert entry.name == "data"
        assert entry.type == "directory"

    @respx.mock
    def test_make_dir_existing_returns_gracefully(self):
        cap = _make_capsule()
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/mkdir").respond(
            409,
            json={"error": {"code": "conflict", "message": "already exists"}},
        )
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/list").respond(
            200,
            json={
                "entries": [
                    {
                        "name": "data",
                        "path": "/home/user/data",
                        "type": "directory",
                        "size": 4096,
                        "mode": 16877,
                        "permissions": "drwxr-xr-x",
                        "owner": "root",
                        "group": "root",
                        "modified_at": 1712899200,
                        "symlink_target": None,
                    }
                ]
            },
        )
        entry = cap.files.make_dir("/home/user/data")
        assert entry.name == "data"


class TestFilesRemove:
    @respx.mock
    def test_remove_succeeds(self):
        cap = _make_capsule()
        route = respx.post(f"{BASE}/v1/capsules/cl-abc/files/remove").respond(204)
        cap.files.remove("/home/user/old_data")
        assert route.called

    @respx.mock
    def test_remove_sends_path(self):
        cap = _make_capsule()
        route = respx.post(f"{BASE}/v1/capsules/cl-abc/files/remove").respond(204)
        cap.files.remove("/tmp/test.txt")
        body = json.loads(route.calls[0].request.content)
        assert body["path"] == "/tmp/test.txt"


class TestFilesExists:
    @respx.mock
    def test_exists_true(self):
        cap = _make_capsule()
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/list").respond(
            200,
            json={
                "entries": [
                    {"name": "hello.txt", "path": "/tmp/hello.txt", "type": "file"}
                ]
            },
        )
        assert cap.files.exists("/tmp/hello.txt") is True

    @respx.mock
    def test_exists_false(self):
        cap = _make_capsule()
        respx.post(f"{BASE}/v1/capsules/cl-abc/files/list").respond(
            200, json={"entries": []}
        )
        assert cap.files.exists("/tmp/nope.txt") is False


class TestPtyEventParsing:
    def test_started_event(self):
        raw = {"type": "started", "tag": "pty-a1b2c3d4", "pid": 42}
        event = _parse_pty_event(raw)
        assert event.type == PtyEventType.started
        assert event.pid == 42
        assert event.tag == "pty-a1b2c3d4"

    def test_output_event_base64(self):
        encoded = base64.b64encode(b"ls -la\n").decode()
        raw = {"type": "output", "data": encoded}
        event = _parse_pty_event(raw)
        assert event.type == PtyEventType.output
        assert event.data == b"ls -la\n"

    def test_output_event_empty(self):
        raw = {"type": "output", "data": ""}
        event = _parse_pty_event(raw)
        assert event.data == b""

    def test_exit_event(self):
        raw = {"type": "exit", "exit_code": 0}
        event = _parse_pty_event(raw)
        assert event.type == PtyEventType.exit
        assert event.exit_code == 0

    def test_error_event(self):
        raw = {"type": "error", "data": "process not found", "fatal": True}
        event = _parse_pty_event(raw)
        assert event.type == PtyEventType.error
        assert event.data == "process not found"
        assert event.fatal is True

    def test_ping_event(self):
        raw = {"type": "ping"}
        event = _parse_pty_event(raw)
        assert event.type == PtyEventType.ping


class TestPtySessionWrite:
    def test_write_sends_base64_input(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        session.write(b"ls -la\n")
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "input"
        assert base64.b64decode(sent["data"]) == b"ls -la\n"


class TestPtySessionResize:
    def test_resize_sends_dimensions(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        session.resize(120, 40)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "resize"
        assert sent["cols"] == 120
        assert sent["rows"] == 40

    def test_resize_zero_raises(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        with pytest.raises(ValueError, match="greater than 0"):
            session.resize(0, 40)
        with pytest.raises(ValueError, match="greater than 0"):
            session.resize(80, 0)


class TestPtySessionKill:
    def test_kill_sends_message(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        session.kill()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "kill"


class TestPtySessionIteration:
    def test_iter_yields_events_until_exit(self):
        ws = MagicMock()
        messages = [
            json.dumps({"type": "started", "tag": "pty-abc12345", "pid": 1}),
            json.dumps({"type": "output", "data": base64.b64encode(b"hello").decode()}),
            json.dumps({"type": "exit", "exit_code": 0}),
        ]
        ws.receive_text.side_effect = messages
        session = PtySession(ws, "cl-abc")
        events = list(session)
        assert len(events) == 2
        assert events[0].type == PtyEventType.started
        assert session.tag == "pty-abc12345"
        assert session.pid == 1
        assert events[1].type == PtyEventType.output
        assert events[1].data == b"hello"

    def test_iter_stops_on_fatal_error(self):
        ws = MagicMock()
        messages = [
            json.dumps({"type": "error", "data": "fatal", "fatal": True}),
        ]
        ws.receive_text.side_effect = messages
        session = PtySession(ws, "cl-abc")
        events = list(session)
        assert len(events) == 1
        assert events[0].type == PtyEventType.error

    def test_iter_stops_on_disconnect(self):
        import httpx_ws

        ws = MagicMock()
        ws.receive_text.side_effect = httpx_ws.WebSocketDisconnect()
        session = PtySession(ws, "cl-abc")
        events = list(session)
        assert events == []


class TestPtySessionContextManager:
    def test_exit_kills_and_closes(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        with session:
            pass
        ws.send_text.assert_called()
        ws.close.assert_called()

    def test_exit_ignores_errors(self):
        ws = MagicMock()
        ws.send_text.side_effect = Exception("already closed")
        session = PtySession(ws, "cl-abc")
        with session:
            pass


class TestPtySessionSendStart:
    def test_send_start_with_defaults(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        session._send_start()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "start"
        assert sent["cmd"] == "/bin/bash"
        assert sent["cols"] == 80
        assert sent["rows"] == 24

    def test_send_start_with_all_params(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        session._send_start(
            cmd="/bin/zsh",
            args=["-l"],
            cols=120,
            rows=40,
            envs={"TERM": "xterm-256color"},
            cwd="/home/user",
        )
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["cmd"] == "/bin/zsh"
        assert sent["args"] == ["-l"]
        assert sent["cols"] == 120


class TestPtySessionSendConnect:
    def test_send_connect(self):
        ws = MagicMock()
        session = PtySession(ws, "cl-abc")
        session._send_connect("pty-abc12345")
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "connect"
        assert sent["tag"] == "pty-abc12345"


class TestAsyncPtySession:
    @pytest.mark.asyncio
    async def test_async_write_sends_base64(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        await session.write(b"hello")
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "input"
        assert base64.b64decode(sent["data"]) == b"hello"

    @pytest.mark.asyncio
    async def test_async_resize(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        await session.resize(100, 30)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "resize"
        assert sent["cols"] == 100
        assert sent["rows"] == 30

    @pytest.mark.asyncio
    async def test_async_resize_zero_raises(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        with pytest.raises(ValueError):
            await session.resize(0, 10)

    @pytest.mark.asyncio
    async def test_async_kill(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        await session.kill()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "kill"

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        async with session:
            pass
        ws.send_text.assert_called()
        ws.close.assert_called()

    @pytest.mark.asyncio
    async def test_async_send_start(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        await session._send_start(cmd="/bin/zsh", cols=100, rows=30)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "start"
        assert sent["cmd"] == "/bin/zsh"
        assert sent["cols"] == 100

    @pytest.mark.asyncio
    async def test_async_iteration(self):
        ws = AsyncMock()
        messages = [
            json.dumps({"type": "started", "tag": "pty-xyz", "pid": 5}),
            json.dumps({"type": "output", "data": base64.b64encode(b"hi").decode()}),
            json.dumps({"type": "exit", "exit_code": 0}),
        ]
        ws.receive_text.side_effect = messages
        session = AsyncPtySession(ws, "cl-abc")
        events = []
        async for event in session:
            events.append(event)
        assert len(events) == 2
        assert events[0].type == PtyEventType.started
        assert session.tag == "pty-xyz"
        assert session.pid == 5


class TestExports:
    def test_file_entry_importable(self):
        from wrenn import FileEntry as FE

        assert FE is not None

    def test_pty_session_importable(self):
        from wrenn import PtySession as PS

        assert PS is not None

    def test_async_pty_session_importable(self):
        from wrenn import AsyncPtySession as APS

        assert APS is not None

    def test_pty_event_importable(self):
        from wrenn import PtyEvent as PE
        from wrenn import PtyEventType as PET

        assert PE is not None
        assert PET is not None
