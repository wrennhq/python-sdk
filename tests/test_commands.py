"""Unit tests for wrenn.commands — Commands / AsyncCommands.

Covers payload construction (cwd, envs, tag, timeout), foreground/background
dispatch, base64 response decoding, stream-event parsing, and the
WebSocket-backed ``stream`` / ``connect`` iterators (with a fake WS).
"""

from __future__ import annotations

import base64
import json
from contextlib import asynccontextmanager, contextmanager

import httpx_ws
import pytest
import respx

from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.commands import (
    AsyncCommands,
    CommandHandle,
    CommandResult,
    Commands,
    ProcessInfo,
    StreamErrorEvent,
    StreamEvent,
    StreamExitEvent,
    StreamStartEvent,
    StreamStderrEvent,
    StreamStdoutEvent,
    _decode_exec_response,
    _parse_stream_event,
)

BASE = "https://app.wrenn.dev/api"
CAPSULE_ID = "cl-cmd123"
EXEC_URL = f"{BASE}/v1/capsules/{CAPSULE_ID}/exec"
PROC_URL = f"{BASE}/v1/capsules/{CAPSULE_ID}/processes"


def _make_commands() -> Commands:
    client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
    return Commands(CAPSULE_ID, client.http)


def _make_async_commands() -> AsyncCommands:
    client = AsyncWrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
    return AsyncCommands(CAPSULE_ID, client.http)


# ── _decode_exec_response ─────────────────────────────────────────


class TestDecodeExecResponse:
    def test_plain_text(self):
        result = _decode_exec_response(
            {"stdout": "hello\n", "stderr": "", "exit_code": 0, "duration_ms": 12}
        )
        assert isinstance(result, CommandResult)
        assert result.stdout == "hello\n"
        assert result.exit_code == 0
        assert result.duration_ms == 12

    def test_base64_stdout(self):
        encoded = base64.b64encode(b"binary\xff\x00out").decode()
        result = _decode_exec_response(
            {"stdout": encoded, "encoding": "base64", "exit_code": 0}
        )
        assert "binary" in result.stdout

    def test_base64_stderr(self):
        out = base64.b64encode(b"ok").decode()
        err = base64.b64encode(b"warning").decode()
        result = _decode_exec_response(
            {"stdout": out, "stderr": err, "encoding": "base64", "exit_code": 1}
        )
        assert result.stdout == "ok"
        assert result.stderr == "warning"
        assert result.exit_code == 1

    def test_missing_fields_default(self):
        result = _decode_exec_response({})
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == -1
        assert result.duration_ms is None

    def test_null_stdout_coerced_to_empty(self):
        result = _decode_exec_response({"stdout": None, "stderr": None})
        assert result.stdout == ""
        assert result.stderr == ""


# ── _parse_stream_event ───────────────────────────────────────────


class TestParseStreamEvent:
    def test_start(self):
        event = _parse_stream_event({"type": "start", "pid": 99})
        assert isinstance(event, StreamStartEvent)
        assert event.type == "start"
        assert event.pid == 99

    def test_stdout(self):
        event = _parse_stream_event({"type": "stdout", "data": "out"})
        assert isinstance(event, StreamStdoutEvent)
        assert event.data == "out"

    def test_stderr(self):
        event = _parse_stream_event({"type": "stderr", "data": "err"})
        assert isinstance(event, StreamStderrEvent)
        assert event.data == "err"

    def test_exit(self):
        event = _parse_stream_event({"type": "exit", "exit_code": 7})
        assert isinstance(event, StreamExitEvent)
        assert event.exit_code == 7

    def test_error(self):
        event = _parse_stream_event({"type": "error", "data": "boom"})
        assert isinstance(event, StreamErrorEvent)
        assert event.data == "boom"

    def test_unknown_type(self):
        event = _parse_stream_event({"type": "weird"})
        assert isinstance(event, StreamEvent)
        assert event.type == "weird"

    def test_missing_type(self):
        event = _parse_stream_event({})
        assert event.type == "unknown"

    def test_exit_missing_code_defaults(self):
        event = _parse_stream_event({"type": "exit"})
        assert isinstance(event, StreamExitEvent)
        assert event.exit_code == -1


# ── Commands.run — payload construction ───────────────────────────


class TestRunPayload:
    @respx.mock
    def test_foreground_basic_payload(self):
        route = respx.post(EXEC_URL).respond(200, json={"stdout": "hi", "exit_code": 0})
        result = _make_commands().run("echo hi")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "echo hi"]
        assert body["background"] is False
        assert body["timeout_sec"] == 30
        assert result.stdout == "hi"

    @respx.mock
    def test_cwd_in_payload(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("pwd", cwd="/tmp/work")
        body = json.loads(route.calls[0].request.content)
        assert body["cwd"] == "/tmp/work"

    @respx.mock
    def test_cwd_omitted_when_none(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("pwd")
        body = json.loads(route.calls[0].request.content)
        assert "cwd" not in body

    @respx.mock
    def test_envs_in_payload(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("env", envs={"FOO": "bar", "BAZ": "qux"})
        body = json.loads(route.calls[0].request.content)
        assert body["envs"] == {"FOO": "bar", "BAZ": "qux"}

    @respx.mock
    def test_empty_envs_still_sent(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("env", envs={})
        body = json.loads(route.calls[0].request.content)
        assert body["envs"] == {}

    @respx.mock
    def test_tag_in_payload(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("echo x", tag="my-tag")
        body = json.loads(route.calls[0].request.content)
        assert body["tag"] == "my-tag"

    @respx.mock
    def test_custom_timeout_in_payload(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("sleep 1", timeout=120)
        body = json.loads(route.calls[0].request.content)
        assert body["timeout_sec"] == 120

    @respx.mock
    def test_timeout_none_omits_field(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("echo x", timeout=None)
        body = json.loads(route.calls[0].request.content)
        assert "timeout_sec" not in body

    @respx.mock
    def test_all_kwargs_combined(self):
        route = respx.post(EXEC_URL).respond(200, json={"exit_code": 0})
        _make_commands().run("echo x", timeout=60, envs={"A": "1"}, cwd="/srv", tag="t")
        body = json.loads(route.calls[0].request.content)
        assert body["cwd"] == "/srv"
        assert body["envs"] == {"A": "1"}
        assert body["tag"] == "t"
        assert body["timeout_sec"] == 60


class TestRunBackground:
    @respx.mock
    def test_background_returns_handle(self):
        respx.post(EXEC_URL).respond(200, json={"pid": 1234, "tag": "bg"})
        handle = _make_commands().run("sleep 100", background=True)
        assert isinstance(handle, CommandHandle)
        assert handle.pid == 1234
        assert handle.tag == "bg"
        assert handle.capsule_id == CAPSULE_ID

    @respx.mock
    def test_background_omits_timeout_sec(self):
        route = respx.post(EXEC_URL).respond(200, json={"pid": 1, "tag": "x"})
        _make_commands().run("sleep 100", background=True, timeout=30)
        body = json.loads(route.calls[0].request.content)
        assert "timeout_sec" not in body
        assert body["background"] is True

    @respx.mock
    def test_background_carries_cwd_and_envs(self):
        route = respx.post(EXEC_URL).respond(200, json={"pid": 5, "tag": "t"})
        _make_commands().run(
            "server", background=True, cwd="/app", envs={"PORT": "80"}, tag="srv"
        )
        body = json.loads(route.calls[0].request.content)
        assert body["cwd"] == "/app"
        assert body["envs"] == {"PORT": "80"}
        assert body["tag"] == "srv"

    @respx.mock
    def test_background_missing_pid_defaults_zero(self):
        respx.post(EXEC_URL).respond(200, json={"tag": "x"})
        handle = _make_commands().run("x", background=True)
        assert handle.pid == 0


class TestListAndKill:
    @respx.mock
    def test_list_parses_processes(self):
        respx.get(PROC_URL).respond(
            200,
            json={
                "processes": [
                    {
                        "pid": 10,
                        "tag": "web",
                        "cmd": "/bin/sh",
                        "args": ["-c", "serve"],
                    },
                    {"pid": 11},
                ]
            },
        )
        procs = _make_commands().list()
        assert len(procs) == 2
        assert isinstance(procs[0], ProcessInfo)
        assert procs[0].pid == 10
        assert procs[0].tag == "web"
        assert procs[0].args == ["-c", "serve"]
        assert procs[1].pid == 11
        assert procs[1].tag is None

    @respx.mock
    def test_list_empty(self):
        respx.get(PROC_URL).respond(200, json={"processes": []})
        assert _make_commands().list() == []

    @respx.mock
    def test_list_missing_key(self):
        respx.get(PROC_URL).respond(200, json={})
        assert _make_commands().list() == []

    @respx.mock
    def test_kill_sends_delete(self):
        route = respx.delete(f"{PROC_URL}/42").respond(204)
        _make_commands().kill(42)
        assert route.called

    @respx.mock
    def test_kill_unknown_pid_raises(self):
        from wrenn.exceptions import WrennNotFoundError

        respx.delete(f"{PROC_URL}/999").respond(
            404, json={"error": {"code": "not_found", "message": "no such process"}}
        )
        with pytest.raises(WrennNotFoundError):
            _make_commands().kill(999)


# ── Fake WebSocket plumbing for stream / connect ──────────────────


class _FakeWS:
    """Synchronous fake WebSocket session."""

    def __init__(self, messages: list) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []

    def send_text(self, text: str) -> None:
        self.sent.append(text)

    def receive_json(self) -> dict:
        if not self._messages:
            raise httpx_ws.WebSocketDisconnect()
        msg = self._messages.pop(0)
        if isinstance(msg, Exception):
            raise msg
        return msg


class _AsyncFakeWS:
    """Asynchronous fake WebSocket session."""

    def __init__(self, messages: list) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def receive_json(self) -> dict:
        if not self._messages:
            raise httpx_ws.WebSocketDisconnect()
        msg = self._messages.pop(0)
        if isinstance(msg, Exception):
            raise msg
        return msg


def _patch_sync_ws(monkeypatch, ws: _FakeWS) -> None:
    @contextmanager
    def _fake_connect(url, client):
        yield ws

    monkeypatch.setattr("wrenn.commands.httpx_ws.connect_ws", _fake_connect)


def _patch_async_ws(monkeypatch, ws: _AsyncFakeWS) -> None:
    @asynccontextmanager
    async def _fake_aconnect(url, client):
        yield ws

    monkeypatch.setattr("wrenn.commands.httpx_ws.aconnect_ws", _fake_aconnect)


# ── Commands.stream ───────────────────────────────────────────────


class TestStream:
    def test_stream_sends_shell_wrapped_start(self, monkeypatch):
        ws = _FakeWS([{"type": "exit", "exit_code": 0}])
        _patch_sync_ws(monkeypatch, ws)
        list(_make_commands().stream("echo hi"))
        start = json.loads(ws.sent[0])
        assert start == {"type": "start", "cmd": "/bin/sh", "args": ["-c", "echo hi"]}

    def test_stream_with_explicit_args(self, monkeypatch):
        ws = _FakeWS([{"type": "exit", "exit_code": 0}])
        _patch_sync_ws(monkeypatch, ws)
        list(_make_commands().stream("/usr/bin/env", args=["python", "-V"]))
        start = json.loads(ws.sent[0])
        assert start == {
            "type": "start",
            "cmd": "/usr/bin/env",
            "args": ["python", "-V"],
        }

    def test_stream_yields_events_until_exit(self, monkeypatch):
        ws = _FakeWS(
            [
                {"type": "start", "pid": 3},
                {"type": "stdout", "data": "line1"},
                {"type": "stderr", "data": "warn"},
                {"type": "exit", "exit_code": 0},
                {"type": "stdout", "data": "after-exit-ignored"},
            ]
        )
        _patch_sync_ws(monkeypatch, ws)
        events = list(_make_commands().stream("echo line1"))
        assert [e.type for e in events] == ["start", "stdout", "stderr", "exit"]

    def test_stream_stops_on_error(self, monkeypatch):
        ws = _FakeWS([{"type": "error", "data": "fatal"}])
        _patch_sync_ws(monkeypatch, ws)
        events = list(_make_commands().stream("bad"))
        assert len(events) == 1
        assert events[0].type == "error"

    def test_stream_handles_disconnect(self, monkeypatch):
        ws = _FakeWS([{"type": "stdout", "data": "x"}])  # then disconnect
        _patch_sync_ws(monkeypatch, ws)
        events = list(_make_commands().stream("echo x"))
        assert [e.type for e in events] == ["stdout"]


# ── Commands.connect ──────────────────────────────────────────────


class TestConnect:
    def test_connect_yields_until_exit(self, monkeypatch):
        ws = _FakeWS(
            [
                {"type": "stdout", "data": "tick"},
                {"type": "exit", "exit_code": 0},
            ]
        )
        _patch_sync_ws(monkeypatch, ws)
        events = list(_make_commands().connect(55))
        assert [e.type for e in events] == ["stdout", "exit"]

    def test_connect_handles_disconnect(self, monkeypatch):
        ws = _FakeWS([])  # immediate disconnect
        _patch_sync_ws(monkeypatch, ws)
        assert list(_make_commands().connect(1)) == []


# ── AsyncCommands ─────────────────────────────────────────────────


class TestAsyncCommands:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_run_payload(self):
        route = respx.post(EXEC_URL).respond(200, json={"stdout": "hi", "exit_code": 0})
        cmds = _make_async_commands()
        result = await cmds.run("echo hi", cwd="/tmp", envs={"K": "v"}, tag="z")
        body = json.loads(route.calls[0].request.content)
        assert body["cwd"] == "/tmp"
        assert body["envs"] == {"K": "v"}
        assert body["tag"] == "z"
        assert result.stdout == "hi"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_run_background(self):
        respx.post(EXEC_URL).respond(200, json={"pid": 7, "tag": "bg"})
        handle = await _make_async_commands().run("sleep 1", background=True)
        assert isinstance(handle, CommandHandle)
        assert handle.pid == 7

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_list(self):
        respx.get(PROC_URL).respond(200, json={"processes": [{"pid": 1, "tag": "a"}]})
        procs = await _make_async_commands().list()
        assert len(procs) == 1
        assert procs[0].pid == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_kill(self):
        route = respx.delete(f"{PROC_URL}/3").respond(204)
        await _make_async_commands().kill(3)
        assert route.called

    @pytest.mark.asyncio
    async def test_async_stream(self, monkeypatch):
        ws = _AsyncFakeWS(
            [
                {"type": "start", "pid": 1},
                {"type": "stdout", "data": "out"},
                {"type": "exit", "exit_code": 0},
            ]
        )
        _patch_async_ws(monkeypatch, ws)
        events = [e async for e in _make_async_commands().stream("echo out")]
        assert [e.type for e in events] == ["start", "stdout", "exit"]
        start = json.loads(ws.sent[0])
        assert start["cmd"] == "/bin/sh"

    @pytest.mark.asyncio
    async def test_async_connect(self, monkeypatch):
        ws = _AsyncFakeWS([{"type": "exit", "exit_code": 0}])
        _patch_async_ws(monkeypatch, ws)
        events = [e async for e in _make_async_commands().connect(9)]
        assert [e.type for e in events] == ["exit"]
