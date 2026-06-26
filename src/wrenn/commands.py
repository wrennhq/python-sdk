from __future__ import annotations

import base64
import builtins
import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Literal, overload

import httpx
import httpx_ws

from wrenn.exceptions import handle_response

# Both signal a terminated WebSocket: ``WebSocketDisconnect`` is a clean close,
# ``WebSocketNetworkError`` an abrupt one. The Wrenn server closes exec/process
# streams abruptly, so iterators must treat either as end-of-stream.
_WS_CLOSED = (httpx_ws.WebSocketDisconnect, httpx_ws.WebSocketNetworkError)


@dataclass
class CommandResult:
    """Result from a foreground command execution."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int | None = None


@dataclass
class CommandHandle:
    """Handle for a background process."""

    pid: int
    tag: str
    capsule_id: str


@dataclass
class ProcessInfo:
    """Information about a running process."""

    pid: int
    tag: str | None = None
    cmd: str | None = None
    args: list[str] | None = None


class StreamEvent:
    """Base class for streaming exec events."""

    __slots__ = ("type",)

    def __init__(self, type: str) -> None:
        self.type = type


class StreamStartEvent(StreamEvent):
    __slots__ = ("pid",)

    def __init__(self, pid: int) -> None:
        super().__init__("start")
        self.pid = pid


class StreamStdoutEvent(StreamEvent):
    __slots__ = ("data",)

    def __init__(self, data: str) -> None:
        super().__init__("stdout")
        self.data = data


class StreamStderrEvent(StreamEvent):
    __slots__ = ("data",)

    def __init__(self, data: str) -> None:
        super().__init__("stderr")
        self.data = data


class StreamExitEvent(StreamEvent):
    __slots__ = ("exit_code",)

    def __init__(self, exit_code: int) -> None:
        super().__init__("exit")
        self.exit_code = exit_code


class StreamErrorEvent(StreamEvent):
    __slots__ = ("data",)

    def __init__(self, data: str) -> None:
        super().__init__("error")
        self.data = data


def _parse_stream_event(raw: dict) -> StreamEvent:
    t = raw.get("type")
    if t == "start":
        return StreamStartEvent(pid=raw.get("pid", 0))
    if t == "stdout":
        return StreamStdoutEvent(data=raw.get("data", ""))
    if t == "stderr":
        return StreamStderrEvent(data=raw.get("data", ""))
    if t == "exit":
        return StreamExitEvent(exit_code=raw.get("exit_code", -1))
    if t == "error":
        return StreamErrorEvent(data=raw.get("data", ""))
    return StreamEvent(type=t or "unknown")


def _build_exec_payload(
    cmd: str,
    background: bool,
    timeout: int | None,
    envs: dict[str, str] | None,
    cwd: str | None,
    tag: str | None,
) -> dict:
    payload: dict = {
        "cmd": cmd,
        "background": background,
    }
    if timeout is not None and not background:
        payload["timeout_sec"] = timeout
    if envs is not None:
        payload["envs"] = envs
    if cwd is not None:
        payload["cwd"] = cwd
    if tag is not None:
        payload["tag"] = tag
    return payload


def _exec_http_timeout(background: bool, timeout: int | None) -> httpx.Timeout | None:
    if not background and timeout is not None:
        return httpx.Timeout(timeout + 10, connect=5.0)
    return None


def _decode_exec_run(
    data: dict, capsule_id: str, background: bool
) -> CommandResult | CommandHandle:
    if background:
        return CommandHandle(
            pid=data.get("pid", 0),
            tag=data.get("tag", ""),
            capsule_id=capsule_id,
        )
    return _decode_exec_response(data)


def _build_stream_start(cmd: str, args: builtins.list[str] | None) -> dict:
    if args:
        return {"type": "start", "cmd": cmd, "args": args}
    return {"type": "start", "cmd": cmd}


def _decode_exec_response(data: dict) -> CommandResult:
    stdout = data.get("stdout") or ""
    stderr = data.get("stderr") or ""
    if data.get("encoding") == "base64":
        stdout = base64.b64decode(stdout).decode("utf-8", errors="replace")
        if stderr:
            stderr = base64.b64decode(stderr).decode("utf-8", errors="replace")
    return CommandResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=data.get("exit_code", -1),
        duration_ms=data.get("duration_ms"),
    )


class Commands:
    """Sync command execution interface. Accessed via ``capsule.commands``."""

    def __init__(self, capsule_id: str, http: httpx.Client) -> None:
        self._capsule_id = capsule_id
        self._http = http

    @overload
    def run(
        self,
        cmd: str,
        *,
        background: Literal[False] = ...,
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None,
    ) -> CommandResult: ...

    @overload
    def run(
        self,
        cmd: str,
        *,
        background: Literal[True],
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None,
    ) -> CommandHandle: ...

    def run(
        self,
        cmd: str,
        *,
        background: bool = False,
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None,
    ) -> CommandResult | CommandHandle:
        """Execute a shell command inside the capsule.

        Args:
            cmd (str): Command string to execute. Sent verbatim to the
                server — no shell wrapping is applied. Provide a full
                shell-quoted command if you need shell features.
            background (bool): If ``True``, launch the process in the
                background and return a :class:`CommandHandle` immediately.
                Defaults to ``False``.
            timeout (int | None): Seconds before the foreground command times
                out. Ignored for background commands. Defaults to ``30``.
            envs (dict[str, str] | None): Additional environment variables
                to set for the process.
            cwd (str | None): Working directory for the process.
            tag (str | None): Optional label attached to background processes
                for later retrieval via :meth:`connect`.

        Returns:
            CommandResult: stdout, stderr, exit code, and duration for
            foreground commands (``background=False``).

            CommandHandle: PID and tag for background commands
            (``background=True``).
        """
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/exec",
            json=_build_exec_payload(cmd, background, timeout, envs, cwd, tag),
            timeout=_exec_http_timeout(background, timeout),
        )
        data = handle_response(resp)
        assert isinstance(data, dict)
        return _decode_exec_run(data, self._capsule_id, background)

    def list(self) -> list[ProcessInfo]:
        """List all running background processes in the capsule.

        Returns:
            list[ProcessInfo]: Running processes with their PID, tag, and
            command information.
        """
        resp = self._http.get(f"/v1/capsules/{self._capsule_id}/processes")
        data = handle_response(resp)
        assert isinstance(data, dict)
        return [
            ProcessInfo(
                pid=p.get("pid", 0),
                tag=p.get("tag"),
                cmd=p.get("cmd"),
                args=p.get("args"),
            )
            for p in data.get("processes", [])
        ]

    def kill(self, pid: int) -> None:
        """Send SIGKILL to a background process.

        Args:
            pid (int): PID of the process to kill.

        Raises:
            WrennNotFoundError: If no process with the given PID exists.
        """
        resp = self._http.delete(f"/v1/capsules/{self._capsule_id}/processes/{pid}")
        handle_response(resp)

    def connect(self, pid: int) -> Iterator[StreamEvent]:
        """Connect to a running background process and stream its output.

        Args:
            pid (int): PID of the background process to attach to.

        Yields:
            StreamEvent: Successive output events. Stops on
            :class:`StreamExitEvent` or :class:`StreamErrorEvent`.
        """
        with httpx_ws.connect_ws(
            f"/v1/capsules/{self._capsule_id}/processes/{pid}/stream",
            self._http,
        ) as ws:  # type: httpx_ws.WebSocketSession
            while True:
                try:
                    raw = ws.receive_json()
                    event = _parse_stream_event(raw)
                    yield event
                    if event.type in ("exit", "error"):
                        break
                except _WS_CLOSED:
                    break

    def stream(
        self, cmd: str, args: builtins.list[str] | None = None
    ) -> Iterator[StreamEvent]:
        """Execute a command via WebSocket, streaming output as events.

        Args:
            cmd (str): Command to execute. Sent verbatim to the server as
                the full command string.
            args (list[str] | None): Optional explicit argument vector. When
                provided, *cmd* is treated as the program and *args* as its
                argv tail. When omitted, *cmd* is forwarded as-is.

        Yields:
            StreamEvent: Successive events including :class:`StreamStartEvent`,
            :class:`StreamStdoutEvent`, :class:`StreamStderrEvent`,
            :class:`StreamExitEvent`, and :class:`StreamErrorEvent`.
        """
        with httpx_ws.connect_ws(
            f"/v1/capsules/{self._capsule_id}/exec/stream",
            self._http,
        ) as ws:  # type: httpx_ws.WebSocketSession
            ws.send_text(json.dumps(_build_stream_start(cmd, args)))
            while True:
                try:
                    raw = ws.receive_json()
                    event = _parse_stream_event(raw)
                    yield event
                    if event.type in ("exit", "error"):
                        break
                except _WS_CLOSED:
                    break


class AsyncCommands:
    """Async command execution interface. Accessed via ``capsule.commands``."""

    def __init__(self, capsule_id: str, http: httpx.AsyncClient) -> None:
        self._capsule_id = capsule_id
        self._http = http

    @overload
    async def run(
        self,
        cmd: str,
        *,
        background: Literal[False] = ...,
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None,
    ) -> CommandResult: ...

    @overload
    async def run(
        self,
        cmd: str,
        *,
        background: Literal[True],
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None,
    ) -> CommandHandle: ...

    async def run(
        self,
        cmd: str,
        *,
        background: bool = False,
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None,
    ) -> CommandResult | CommandHandle:
        """Execute a shell command inside the capsule.

        Args:
            cmd (str): Command string to execute. Sent verbatim to the
                server — no shell wrapping is applied. Provide a full
                shell-quoted command if you need shell features.
            background (bool): If ``True``, launch the process in the
                background and return a :class:`CommandHandle` immediately.
                Defaults to ``False``.
            timeout (int | None): Seconds before the foreground command times
                out. Ignored for background commands. Defaults to ``30``.
            envs (dict[str, str] | None): Additional environment variables
                to set for the process.
            cwd (str | None): Working directory for the process.
            tag (str | None): Optional label attached to background processes
                for later retrieval via :meth:`connect`.

        Returns:
            CommandResult: stdout, stderr, exit code, and duration for
            foreground commands (``background=False``).

            CommandHandle: PID and tag for background commands
            (``background=True``).
        """
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/exec",
            json=_build_exec_payload(cmd, background, timeout, envs, cwd, tag),
            timeout=_exec_http_timeout(background, timeout),
        )
        data = handle_response(resp)
        assert isinstance(data, dict)
        return _decode_exec_run(data, self._capsule_id, background)

    async def list(self) -> list[ProcessInfo]:
        """List all running background processes in the capsule.

        Returns:
            list[ProcessInfo]: Running processes with their PID, tag, and
            command information.
        """
        resp = await self._http.get(f"/v1/capsules/{self._capsule_id}/processes")
        data = handle_response(resp)
        assert isinstance(data, dict)
        return [
            ProcessInfo(
                pid=p.get("pid", 0),
                tag=p.get("tag"),
                cmd=p.get("cmd"),
                args=p.get("args"),
            )
            for p in data.get("processes", [])
        ]

    async def kill(self, pid: int) -> None:
        """Send SIGKILL to a background process.

        Args:
            pid (int): PID of the process to kill.

        Raises:
            WrennNotFoundError: If no process with the given PID exists.
        """
        resp = await self._http.delete(
            f"/v1/capsules/{self._capsule_id}/processes/{pid}"
        )
        handle_response(resp)

    async def connect(self, pid: int) -> AsyncIterator[StreamEvent]:
        """Connect to a running background process and stream its output.

        Args:
            pid (int): PID of the background process to attach to.

        Yields:
            StreamEvent: Successive output events. Stops on
            :class:`StreamExitEvent` or :class:`StreamErrorEvent`.
        """
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self._capsule_id}/processes/{pid}/stream",
            self._http,
        ) as ws:  # type: httpx_ws.AsyncWebSocketSession
            try:
                while True:
                    raw = await ws.receive_json()
                    event = _parse_stream_event(raw)
                    yield event
                    if event.type in ("exit", "error"):
                        break
            except _WS_CLOSED:
                pass

    async def stream(
        self, cmd: str, args: builtins.list[str] | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Execute a command via WebSocket, streaming output as events.

        Args:
            cmd (str): Command to execute. Sent verbatim to the server as
                the full command string.
            args (list[str] | None): Optional explicit argument vector. When
                provided, *cmd* is treated as the program and *args* as its
                argv tail. When omitted, *cmd* is forwarded as-is.

        Yields:
            StreamEvent: Successive events including :class:`StreamStartEvent`,
            :class:`StreamStdoutEvent`, :class:`StreamStderrEvent`,
            :class:`StreamExitEvent`, and :class:`StreamErrorEvent`.
        """
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self._capsule_id}/exec/stream",
            self._http,
        ) as ws:  # type: httpx_ws.AsyncWebSocketSession
            await ws.send_text(json.dumps(_build_stream_start(cmd, args)))
            try:
                while True:
                    raw = await ws.receive_json()
                    event = _parse_stream_event(raw)
                    yield event
                    if event.type in ("exit", "error"):
                        break
            except _WS_CLOSED:
                pass
