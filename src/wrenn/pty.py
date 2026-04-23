from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Iterator
from enum import StrEnum
from typing import Any

import httpx_ws
from pydantic import BaseModel


class PtyEventType(StrEnum):
    started = "started"
    output = "output"
    exit = "exit"
    error = "error"
    ping = "ping"


class PtyEvent(BaseModel):
    type: PtyEventType
    pid: int | None = None
    tag: str | None = None
    data: bytes | str | None = None
    exit_code: int | None = None
    fatal: bool | None = None


def _parse_pty_event(raw: dict[str, Any]) -> PtyEvent:
    msg_type = raw.get("type", "")
    if msg_type == "started":
        return PtyEvent(
            type=PtyEventType.started,
            pid=raw.get("pid"),
            tag=raw.get("tag"),
        )
    if msg_type == "output":
        raw_data = raw.get("data", "")
        decoded = base64.b64decode(raw_data) if raw_data else b""
        return PtyEvent(type=PtyEventType.output, data=decoded)
    if msg_type == "exit":
        return PtyEvent(type=PtyEventType.exit, exit_code=raw.get("exit_code", -1))
    if msg_type == "error":
        return PtyEvent(
            type=PtyEventType.error,
            data=raw.get("data", ""),
            fatal=raw.get("fatal", False),
        )
    if msg_type == "ping":
        return PtyEvent(type=PtyEventType.ping)
    return PtyEvent(type=PtyEventType(msg_type) if msg_type else PtyEventType.ping)


class PtySession:
    """Interactive PTY session backed by a WebSocket.

    Use as a context manager and iterate over events::

        with sb.pty(cmd="/bin/bash") as term:
            term.write(b"ls -la\\n")
            for event in term:
                if event.type == "output":
                    sys.stdout.buffer.write(event.data)
                elif event.type == "exit":
                    break
    """

    def __init__(self, ws: httpx_ws.WebSocketSession, capsule_id: str) -> None:
        self._ws = ws
        self._capsule_id = capsule_id
        self._tag: str | None = None
        self._pid: int | None = None
        self._done = False

    @property
    def tag(self) -> str | None:
        """Session tag. Available after the ``started`` event."""
        return self._tag

    @property
    def pid(self) -> int | None:
        """Process PID. Available after the ``started`` event."""
        return self._pid

    def _send_start(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        msg: dict[str, Any] = {
            "type": "start",
            "cmd": cmd,
            "cols": cols or 80,
            "rows": rows or 24,
        }
        if args:
            msg["args"] = args
        if envs:
            msg["envs"] = envs
        if cwd:
            msg["cwd"] = cwd
        self._ws.send_text(json.dumps(msg))

    def _send_connect(self, tag: str) -> None:
        self._ws.send_text(json.dumps({"type": "connect", "tag": tag}))

    def write(self, data: bytes) -> None:
        """Send raw bytes to the PTY stdin.

        Args:
            data: Raw bytes to send. Base64-encoded internally.
        """
        encoded = base64.b64encode(data).decode("ascii")
        self._ws.send_text(json.dumps({"type": "input", "data": encoded}))

    def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY terminal.

        Args:
            cols: New column count. Must be > 0.
            rows: New row count. Must be > 0.

        Raises:
            ValueError: If cols or rows is 0.
        """
        if cols <= 0 or rows <= 0:
            raise ValueError("cols and rows must be greater than 0")
        self._ws.send_text(json.dumps({"type": "resize", "cols": cols, "rows": rows}))

    def kill(self) -> None:
        """Send SIGKILL to the PTY process."""
        self._ws.send_text(json.dumps({"type": "kill"}))

    def __iter__(self) -> Iterator[PtyEvent]:
        return self

    def __next__(self) -> PtyEvent:
        if self._done:
            raise StopIteration
        try:
            raw = self._ws.receive_text()
        except httpx_ws.WebSocketDisconnect:
            raise StopIteration
        event = _parse_pty_event(json.loads(raw))
        if event.type == PtyEventType.started:
            if event.tag is not None:
                self._tag = event.tag
            if event.pid is not None:
                self._pid = event.pid
        if event.type == PtyEventType.exit:
            raise StopIteration
        if event.type == PtyEventType.error and event.fatal:
            self._done = True
            return event
        return event

    def __enter__(self) -> PtySession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            self.kill()
        except Exception:
            pass
        try:
            self._ws.close()
        except Exception:
            pass


class AsyncPtySession:
    """Async interactive PTY session backed by a WebSocket.

    Use as an async context manager and async iterate over events::

        async with sb.pty(cmd="/bin/bash") as term:
            await term.write(b"ls -la\\n")
            async for event in term:
                if event.type == "output":
                    sys.stdout.buffer.write(event.data)
                elif event.type == "exit":
                    break
    """

    def __init__(self, ws: httpx_ws.AsyncWebSocketSession, capsule_id: str) -> None:
        self._ws = ws
        self._capsule_id = capsule_id
        self._tag: str | None = None
        self._pid: int | None = None
        self._done = False

    @property
    def tag(self) -> str | None:
        """Session tag. Available after the ``started`` event."""
        return self._tag

    @property
    def pid(self) -> int | None:
        """Process PID. Available after the ``started`` event."""
        return self._pid

    async def _send_start(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        msg: dict[str, Any] = {
            "type": "start",
            "cmd": cmd,
            "cols": cols or 80,
            "rows": rows or 24,
        }
        if args:
            msg["args"] = args
        if envs:
            msg["envs"] = envs
        if cwd:
            msg["cwd"] = cwd
        await self._ws.send_text(json.dumps(msg))

    async def _send_connect(self, tag: str) -> None:
        await self._ws.send_text(json.dumps({"type": "connect", "tag": tag}))

    async def write(self, data: bytes) -> None:
        """Send raw bytes to the PTY stdin.

        Args:
            data: Raw bytes to send. Base64-encoded internally.
        """
        encoded = base64.b64encode(data).decode("ascii")
        await self._ws.send_text(json.dumps({"type": "input", "data": encoded}))

    async def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY terminal.

        Args:
            cols: New column count. Must be > 0.
            rows: New row count. Must be > 0.

        Raises:
            ValueError: If cols or rows is 0.
        """
        if cols <= 0 or rows <= 0:
            raise ValueError("cols and rows must be greater than 0")
        await self._ws.send_text(
            json.dumps({"type": "resize", "cols": cols, "rows": rows})
        )

    async def kill(self) -> None:
        """Send SIGKILL to the PTY process."""
        await self._ws.send_text(json.dumps({"type": "kill"}))

    def __aiter__(self) -> AsyncIterator[PtyEvent]:
        return self

    async def __anext__(self) -> PtyEvent:
        if self._done:
            raise StopAsyncIteration
        try:
            raw = await self._ws.receive_text()
        except httpx_ws.WebSocketDisconnect:
            raise StopAsyncIteration
        event = _parse_pty_event(json.loads(raw))
        if event.type == PtyEventType.started:
            if event.tag is not None:
                self._tag = event.tag
            if event.pid is not None:
                self._pid = event.pid
        if event.type == PtyEventType.exit:
            raise StopAsyncIteration
        if event.type == PtyEventType.error and event.fatal:
            self._done = True
            return event
        return event

    async def __aenter__(self) -> AsyncPtySession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            await self.kill()
        except Exception:
            pass
        try:
            await self._ws.close()
        except Exception:
            pass
