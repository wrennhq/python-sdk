from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import respx

from wrenn.client import WrennClient
from wrenn.models import FileEntry
from wrenn.pty import (
    AsyncPtySession,
    PtyEventType,
    PtySession,
    _parse_pty_event,
)
from wrenn.sandbox import Sandbox


@pytest.fixture
def client():
    with WrennClient(api_key="wrn_test1234567890abcdef12345678") as c:
        yield c


def _make_sandbox(client: WrennClient, sb_id: str = "cl-abc") -> Sandbox:
    respx.post("https://api.wrenn.dev/v1/sandboxes").respond(
        201, json={"id": sb_id, "status": "running"}
    )
    return client.sandboxes.create()


class TestListDir:
    @respx.mock
    def test_list_dir_returns_entries(self, client):
        sb = _make_sandbox(client)
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/list").respond(
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
        entries = sb.list_dir("/home/user")
        assert len(entries) == 2
        assert isinstance(entries[0], FileEntry)
        assert entries[0].name == "main.py"
        assert entries[0].type == "file"
        assert entries[1].name == "config"
        assert entries[1].type == "directory"

    @respx.mock
    def test_list_dir_with_depth(self, client):
        sb = _make_sandbox(client)
        route = respx.post(
            "https://api.wrenn.dev/v1/sandboxes/cl-abc/files/list"
        ).respond(200, json={"entries": []})
        sb.list_dir("/home/user", depth=3)
        body = json.loads(route.calls[0].request.content)
        assert body["depth"] == 3

    @respx.mock
    def test_list_dir_empty(self, client):
        sb = _make_sandbox(client)
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/list").respond(
            200, json={"entries": []}
        )
        entries = sb.list_dir("/empty")
        assert entries == []

    @respx.mock
    def test_list_dir_symlink(self, client):
        sb = _make_sandbox(client)
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/list").respond(
            200,
            json={
                "entries": [
                    {
                        "name": "link",
                        "path": "/home/user/link",
                        "type": "symlink",
                        "size": 4,
                        "mode": 41471,
                        "permissions": "lrwxrwxrwx",
                        "owner": "root",
                        "group": "root",
                        "modified_at": 1712899000,
                        "symlink_target": "/bin",
                    }
                ]
            },
        )
        entries = sb.list_dir("/home/user")
        assert len(entries) == 1
        assert entries[0].type == "symlink"
        assert entries[0].symlink_target == "/bin"


class TestMkdir:
    @respx.mock
    def test_mkdir_returns_entry(self, client):
        sb = _make_sandbox(client)
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/mkdir").respond(
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
        entry = sb.mkdir("/home/user/data")
        assert isinstance(entry, FileEntry)
        assert entry.name == "data"
        assert entry.type == "directory"

    @respx.mock
    def test_mkdir_existing_returns_gracefully(self, client):
        sb = _make_sandbox(client)
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/mkdir").respond(
            409,
            json={"error": {"code": "conflict", "message": "already exists"}},
        )
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/list").respond(
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
        entry = sb.mkdir("/home/user/data")
        assert entry.name == "data"


class TestRemove:
    @respx.mock
    def test_remove_succeeds(self, client):
        sb = _make_sandbox(client)
        route = respx.post(
            "https://api.wrenn.dev/v1/sandboxes/cl-abc/files/remove"
        ).respond(204)
        sb.remove("/home/user/old_data")
        assert route.called

    @respx.mock
    def test_remove_sends_path(self, client):
        sb = _make_sandbox(client)
        route = respx.post(
            "https://api.wrenn.dev/v1/sandboxes/cl-abc/files/remove"
        ).respond(204)
        sb.remove("/tmp/test.txt")
        body = json.loads(route.calls[0].request.content)
        assert body["path"] == "/tmp/test.txt"


class TestUpload:
    @respx.mock
    def test_upload_sends_multipart(self, client):
        sb = _make_sandbox(client)
        route = respx.post(
            "https://api.wrenn.dev/v1/sandboxes/cl-abc/files/write"
        ).respond(204)
        sb.upload("/app/main.py", b"print('hello')")
        assert route.called
        req = route.calls[0].request
        assert b"multipart/form-data" in req.headers.get("content-type", "").encode()

    @respx.mock
    def test_download_returns_bytes(self, client):
        sb = _make_sandbox(client)
        content = b"file contents here"
        respx.post("https://api.wrenn.dev/v1/sandboxes/cl-abc/files/read").respond(
            200, content=content
        )
        data = sb.download("/app/main.py")
        assert data == content


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

    def test_error_event_non_fatal(self):
        raw = {"type": "error", "data": "something", "fatal": False}
        event = _parse_pty_event(raw)
        assert event.fatal is False

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
        assert sent["rows"] == 40
        assert sent["envs"] == {"TERM": "xterm-256color"}
        assert sent["cwd"] == "/home/user"


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
        assert sent["rows"] == 30

    @pytest.mark.asyncio
    async def test_async_send_connect(self):
        ws = AsyncMock()
        session = AsyncPtySession(ws, "cl-abc")
        await session._send_connect("pty-abc12345")
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "connect"
        assert sent["tag"] == "pty-abc12345"

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
        from wrenn import PtyEvent as PE, PtyEventType as PET

        assert PE is not None
        assert PET is not None
