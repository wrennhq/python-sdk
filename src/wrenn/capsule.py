from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
import warnings
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import httpx
import httpx_ws

from wrenn.exceptions import handle_response
from wrenn.models import (
    BackgroundExecResponse,
    CapsuleMetrics,
    ExecResponse,
    FileEntry,
    ListDirResponse,
    MakeDirResponse,
    ProcessListResponse,
    Status,
)
from wrenn.models import (
    Capsule as CapsuleModel,
)
from wrenn.pty import AsyncPtySession, PtySession


class ExecResult:
    """Typed result from a synchronous exec call."""

    __slots__ = ("stdout", "stderr", "exit_code", "duration_ms", "encoding")

    def __init__(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: int | None,
        encoding: str | None,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_ms = duration_ms
        self.encoding = encoding


class CodeResult:
    """Typed result from stateful code execution (``run_code``).

    Attributes:
        text: text/plain representation of the result.
        data: rich MIME bundle (e.g. ``{"image/png": "..."}``).
        stdout: accumulated stdout output.
        stderr: accumulated stderr output.
        error: language-specific error/traceback string.
    """

    __slots__ = ("text", "data", "stdout", "stderr", "error")

    def __init__(
        self,
        text: str | None = None,
        data: dict[str, str] | None = None,
        stdout: str = "",
        stderr: str = "",
        error: str | None = None,
    ) -> None:
        self.text = text
        self.data = data
        self.stdout = stdout
        self.stderr = stderr
        self.error = error


class StreamEvent:
    """Base class for streaming exec events."""

    __slots__ = ("type",)

    def __init__(self, type: str) -> None:
        self.type = type


class StreamStartEvent(StreamEvent):
    """Process started."""

    __slots__ = ("pid",)

    def __init__(self, pid: int) -> None:
        super().__init__("start")
        self.pid = pid


class StreamStdoutEvent(StreamEvent):
    """Stdout data received."""

    __slots__ = ("data",)

    def __init__(self, data: str) -> None:
        super().__init__("stdout")
        self.data = data


class StreamStderrEvent(StreamEvent):
    """Stderr data received."""

    __slots__ = ("data",)

    def __init__(self, data: str) -> None:
        super().__init__("stderr")
        self.data = data


class StreamExitEvent(StreamEvent):
    """Process exited."""

    __slots__ = ("exit_code",)

    def __init__(self, exit_code: int) -> None:
        super().__init__("exit")
        self.exit_code = exit_code


class StreamErrorEvent(StreamEvent):
    """Error occurred."""

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


def _build_proxy_url(base_url: str, capsule_id: str | None, port: int) -> str:
    parsed = httpx.URL(base_url)
    host = parsed.host
    if parsed.port:
        host = f"{host}:{parsed.port}"
    scheme = "ws" if parsed.scheme == "http" else "wss"
    return f"{scheme}://{port}-{capsule_id}.{host}"


class Capsule(CapsuleModel):
    """Developer-facing capsule interface wrapping the generated Capsule model.

    Provides data-plane methods (exec, file I/O, lifecycle), capsule proxy
    helpers, and context-manager support for automatic cleanup.
    """

    _http: httpx.Client | None = None
    _async_http: httpx.AsyncClient | None = None
    _base_url: str = ""
    _api_key: str | None = None
    _token: str | None = None
    _proxy_client: httpx.Client | None = None
    _async_proxy_client: httpx.AsyncClient | None = None
    _kernel_id: str | None = None
    _jupyter_ws: Any = None
    _async_jupyter_ws: Any = None

    def _bind(
        self,
        http: httpx.Client | httpx.AsyncClient,
        base_url: str,
        api_key: str | None = None,
        token: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._token = token
        self._proxy_client = None
        self._async_proxy_client = None
        self._kernel_id = None
        self._jupyter_ws = None
        self._async_jupyter_ws = None
        if isinstance(http, httpx.Client):
            self._http = http
            self._async_http = None
        else:
            self._http = None  # type: ignore[assignment]
            self._async_http = http

    def _proxy_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _clear_content_type(self) -> dict[str, str]:
        assert self._http is not None
        headers = dict(self._http.headers)
        headers.pop("Content-Type", None)
        return headers

    def _async_clear_content_type(self) -> dict[str, str]:
        assert self._async_http is not None
        headers = dict(self._async_http.headers)
        headers.pop("Content-Type", None)
        return headers

    def get_url(self, port: int) -> str:
        """Construct the proxy URL for a port inside this capsule.

        Args:
            port: Port number of the service running inside the capsule.

        Returns:
            A URL string like ``http://8888-cl-abc123.api.wrenn.dev``.
        """
        return _build_proxy_url(self._base_url, self.id, port)

    @property
    def http_client(self) -> httpx.Client:
        """A pre-configured ``httpx.Client`` targeting the capsule proxy on port 8888.

        The client has auth headers set and ``base_url`` pointing to
        the proxy URL for port 8888.  Closed automatically when the capsule exits.
        """
        if self._proxy_client is None:
            url = (
                _build_proxy_url(self._base_url, self.id, 8888)
                .replace("ws://", "http://")
                .replace("wss://", "https://")
            )
            self._proxy_client = httpx.Client(
                base_url=url,
                headers=self._proxy_headers(),
            )
        return self._proxy_client

    def wait_ready(self, timeout: float = 30, interval: float = 0.5) -> None:
        """Block until the capsule status is ``running``.

        Args:
            timeout: Maximum seconds to wait.
            interval: Seconds between polls.

        Raises:
            TimeoutError: If the capsule does not become ready in time.
        """
        assert self._http is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = self._http.get(f"/v1/capsules/{self.id}")
            data = resp.json()
            status = data.get("status")
            if status == Status.running:
                self.status = Status.running
                return
            if status in (Status.error, Status.stopped):
                raise RuntimeError(f"Capsule entered {status} state while waiting")
            time.sleep(interval)
        raise TimeoutError(f"Capsule {self.id} did not become ready within {timeout}s")

    async def async_wait_ready(
        self, timeout: float = 30, interval: float = 0.5
    ) -> None:
        """Async version of ``wait_ready``."""
        assert self._async_http is not None
        import asyncio

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = await self._async_http.get(f"/v1/capsules/{self.id}")
            data = resp.json()
            status = data.get("status")
            if status == Status.running:
                self.status = Status.running
                return
            if status in (Status.error, Status.stopped):
                raise RuntimeError(f"Capsule entered {status} state while waiting")
            await asyncio.sleep(interval)
        raise TimeoutError(f"Capsule {self.id} did not become ready within {timeout}s")

    def exec(
        self,
        cmd: str,
        args: list[str] | None = None,
        timeout_sec: int | None = 30,
        background: bool = False,
        tag: str | None = None,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> ExecResult | BackgroundExecResponse:
        """Execute a command synchronously inside the capsule.

        Args:
            cmd: Command to run.
            args: Optional positional arguments.
            timeout_sec: Execution timeout in seconds (foreground only).
            background: If true, start as a background process and return immediately.
            tag: Optional tag for the background process.
            envs: Environment variables (background only).
            cwd: Working directory (background only).

        Returns:
            An ``ExecResult`` for foreground exec, or ``BackgroundExecResponse``
            when ``background=True`` (HTTP 202).
        """
        assert self._http is not None
        payload: dict = {"cmd": cmd}
        if args is not None:
            payload["args"] = args
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        if background:
            payload["background"] = True
        if tag is not None:
            payload["tag"] = tag
        if envs is not None:
            payload["envs"] = envs
        if cwd is not None:
            payload["cwd"] = cwd
        resp = self._http.post(f"/v1/capsules/{self.id}/exec", json=payload)
        if resp.status_code == 202:
            return BackgroundExecResponse.model_validate(resp.json())
        resp.raise_for_status()
        er = ExecResponse.model_validate(resp.json())
        stdout = er.stdout or ""
        stderr = er.stderr or ""
        if er.encoding == "base64":
            stdout = base64.b64decode(stdout).decode("utf-8", errors="replace")
            if stderr:
                stderr = base64.b64decode(stderr).decode("utf-8", errors="replace")
        return ExecResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=er.exit_code if er.exit_code is not None else -1,
            duration_ms=er.duration_ms,
            encoding=er.encoding,
        )

    async def async_exec(
        self,
        cmd: str,
        args: list[str] | None = None,
        timeout_sec: int | None = 30,
        background: bool = False,
        tag: str | None = None,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> ExecResult | BackgroundExecResponse:
        """Async version of ``exec``."""
        assert self._async_http is not None
        payload: dict = {"cmd": cmd}
        if args is not None:
            payload["args"] = args
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        if background:
            payload["background"] = True
        if tag is not None:
            payload["tag"] = tag
        if envs is not None:
            payload["envs"] = envs
        if cwd is not None:
            payload["cwd"] = cwd
        resp = await self._async_http.post(f"/v1/capsules/{self.id}/exec", json=payload)
        if resp.status_code == 202:
            return BackgroundExecResponse.model_validate(resp.json())
        resp.raise_for_status()
        er = ExecResponse.model_validate(resp.json())
        stdout = er.stdout or ""
        stderr = er.stderr or ""
        if er.encoding == "base64":
            stdout = base64.b64decode(stdout).decode("utf-8", errors="replace")
            if stderr:
                stderr = base64.b64decode(stderr).decode("utf-8", errors="replace")
        return ExecResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=er.exit_code if er.exit_code is not None else -1,
            duration_ms=er.duration_ms,
            encoding=er.encoding,
        )

    def exec_stream(
        self,
        cmd: str,
        args: list[str] | None = None,
    ) -> Iterator[StreamEvent]:
        """Execute a command via WebSocket, yielding ``StreamEvent`` objects.

        Args:
            cmd: Command to run.
            args: Optional positional arguments.

        Yields:
            ``StreamStartEvent``, ``StreamStdoutEvent``, ``StreamStderrEvent``,
            ``StreamExitEvent``, or ``StreamErrorEvent``.
        """
        assert self._http is not None
        ws: httpx_ws.WebSocketSession
        with httpx_ws.connect_ws(  # type: ignore[attr-defined]
            f"/v1/capsules/{self.id}/exec/stream",
            self._http,
        ) as ws:
            start_msg: dict = {"type": "start", "cmd": cmd}
            if args:
                start_msg["args"] = args
            ws.send_text(json.dumps(start_msg))
            while True:
                try:
                    raw_data: dict = ws.receive_json()  # type: ignore[assignment]
                    event = _parse_stream_event(raw_data)
                    yield event

                    if event.type in ("exit", "error"):
                        break

                except httpx_ws.WebSocketDisconnect:
                    break

    async def async_exec_stream(
        self, cmd: str, args: list[str] | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Async version of ``exec_stream``."""
        assert self._async_http is not None
        ws: httpx_ws.AsyncWebSocketSession
        async with httpx_ws.aconnect_ws(  # type: ignore[attr-defined, var-annotated]
            f"/v1/capsules/{self.id}/exec/stream", self._async_http
        ) as ws:
            start_msg: dict = {"type": "start", "cmd": cmd}
            if args:
                start_msg["args"] = args
            await ws.send_text(json.dumps(start_msg))

            try:
                while True:
                    raw_data = await ws.receive_json()
                    event = _parse_stream_event(raw_data)
                    yield event

                    if event.type in ("exit", "error"):
                        break
            except httpx_ws.WebSocketDisconnect:
                pass

    def upload(self, path: str, data: bytes) -> None:
        """Upload a small file to the capsule.

        Args:
            path: Absolute destination path inside the capsule.
            data: File contents as bytes.
        """
        assert self._http is not None
        resp = self._http.post(
            f"/v1/capsules/{self.id}/files/write",
            files={"file": ("upload", data)},
            data={"path": path},
        )

        resp.raise_for_status()

    async def async_upload(self, path: str, data: bytes) -> None:
        """Async version of ``upload``."""
        assert self._async_http is not None
        resp = await self._async_http.post(
            f"/v1/capsules/{self.id}/files/write",
            files={"file": ("upload", data)},
            data={"path": path},
        )
        resp.raise_for_status()

    def download(self, path: str) -> bytes:
        """Download a small file from the capsule.

        Args:
            path: Absolute file path inside the capsule.

        Returns:
            File contents as bytes.
        """
        assert self._http is not None
        resp = self._http.post(
            f"/v1/capsules/{self.id}/files/read",
            json={"path": path},
        )
        resp.raise_for_status()
        return resp.content

    async def async_download(self, path: str) -> bytes:
        """Async version of ``download``."""
        assert self._async_http is not None
        resp = await self._async_http.post(
            f"/v1/capsules/{self.id}/files/read",
            json={"path": path},
        )
        resp.raise_for_status()
        return resp.content

    def stream_upload(self, path: str, stream: Iterator[bytes]) -> None:
        """Streaming upload for large files.

        Args:
            path: Absolute destination path inside the capsule.
            stream: An iterator yielding byte chunks.
        """
        assert self._http is not None

        boundary = os.urandom(16).hex().encode("utf-8")

        def _multipart_stream() -> Iterator[bytes]:
            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="path"\r\n\r\n'
            yield path.encode("utf-8") + b"\r\n"

            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="file"; filename="upload.bin"\r\n'
            yield b"Content-Type: application/octet-stream\r\n\r\n"

            for chunk in stream:
                yield chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")

            yield b"\r\n--" + boundary + b"--\r\n"

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary.decode('utf-8')}"
        }

        resp = self._http.post(
            f"/v1/capsules/{self.id}/files/stream/write",
            content=_multipart_stream(),
            headers=headers,
        )
        resp.raise_for_status()

    async def async_stream_upload(
        self, path: str, stream: AsyncIterator[bytes]
    ) -> None:
        """Async version of ``stream_upload``."""
        assert self._async_http is not None

        boundary = os.urandom(16).hex().encode("utf-8")

        async def _async_multipart_stream() -> AsyncIterator[bytes]:
            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="path"\r\n\r\n'
            yield path.encode("utf-8") + b"\r\n"

            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="file"; filename="upload.bin"\r\n'
            yield b"Content-Type: application/octet-stream\r\n\r\n"

            async for chunk in stream:
                yield chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")

            yield b"\r\n--" + boundary + b"--\r\n"

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary.decode('utf-8')}"
        }

        resp = await self._async_http.post(
            f"/v1/capsules/{self.id}/files/stream/write",
            content=_async_multipart_stream(),
            headers=headers,
        )
        resp.raise_for_status()

    def stream_download(self, path: str) -> Iterator[bytes]:
        """Streaming download for large files.

        Args:
            path: Absolute file path inside the capsule.

        Yields:
            Byte chunks.
        """
        assert self._http is not None
        with self._http.stream(
            "POST",
            f"/v1/capsules/{self.id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            yield from resp.iter_bytes()

    async def async_stream_download(self, path: str) -> AsyncIterator[bytes]:
        """Async version of ``stream_download``."""
        assert self._async_http is not None
        async with self._async_http.stream(
            "POST",
            f"/v1/capsules/{self.id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk

    def list_dir(self, path: str, depth: int = 1) -> list[FileEntry]:
        """List directory contents inside the capsule.

        Args:
            path: Absolute directory path.
            depth: Recursion depth. 1 = immediate children only.

        Returns:
            List of FileEntry objects with full metadata.

        Raises:
            WrennValidationError: Invalid path.
            WrennNotFoundError: Capsule or directory not found.
            WrennConflictError: Capsule is not running.
            WrennAgentError: Agent error.
            WrennHostUnavailableError: Host agent not reachable.
        """
        assert self._http is not None
        resp = self._http.post(
            f"/v1/capsules/{self.id}/files/list",
            json={"path": path, "depth": depth},
        )
        data = handle_response(resp)
        parsed = ListDirResponse.model_validate(data)
        return parsed.entries or []

    async def async_list_dir(self, path: str, depth: int = 1) -> list[FileEntry]:
        """Async version of ``list_dir``."""
        assert self._async_http is not None
        resp = await self._async_http.post(
            f"/v1/capsules/{self.id}/files/list",
            json={"path": path, "depth": depth},
        )
        data = handle_response(resp)
        parsed = ListDirResponse.model_validate(data)
        return parsed.entries or []

    def mkdir(self, path: str) -> FileEntry:
        """Create a directory inside the capsule (with parents).

        Args:
            path: Absolute directory path to create.

        Returns:
            FileEntry for the created directory.

        Raises:
            WrennValidationError: Path exists and is not a directory.
            WrennConflictError: Directory already exists (returns existing entry).
                Capsule is not running.
            WrennNotFoundError: Capsule not found.
            WrennAgentError: Agent error.
            WrennHostUnavailableError: Host agent not reachable.
        """
        assert self._http is not None
        resp = self._http.post(
            f"/v1/capsules/{self.id}/files/mkdir",
            json={"path": path},
        )
        if resp.status_code == 409:
            try:
                body = resp.json()
                err = body.get("error", {})
                if err.get("code") == "conflict":
                    parent_dir = os.path.dirname(path)
                    dir_name = os.path.basename(path)

                    listing = self.list_dir(parent_dir, depth=0)
                    for entry in listing:
                        if entry.name == dir_name:
                            return entry
            except Exception:
                pass
        data = handle_response(resp)
        parsed = MakeDirResponse.model_validate(data)
        if parsed.entry is None:
            raise RuntimeError("mkdir response missing entry")
        return parsed.entry

    async def async_mkdir(self, path: str) -> FileEntry:
        """Async version of ``mkdir``."""
        assert self._async_http is not None
        resp = await self._async_http.post(
            f"/v1/capsules/{self.id}/files/mkdir",
            json={"path": path},
        )
        if resp.status_code == 409:
            try:
                body = resp.json()
                err = body.get("error", {})
                if err.get("code") == "conflict":
                    listing = await self.async_list_dir(path, depth=0)
                    parent_dir = os.path.dirname(path)
                    dir_name = os.path.basename(path)

                    listing = self.list_dir(parent_dir, depth=0)
                    for entry in listing:
                        if entry.name == dir_name:
                            return entry
            except Exception:
                pass
        data = handle_response(resp)
        parsed = MakeDirResponse.model_validate(data)
        if parsed.entry is None:
            raise RuntimeError("mkdir response missing entry")
        return parsed.entry

    def remove(self, path: str) -> None:
        """Remove a file or directory inside the capsule.

        Removes recursively. No confirmation or dry-run. Equivalent to rm -rf.

        Args:
            path: Absolute path to remove.

        Raises:
            WrennValidationError: Invalid path.
            WrennNotFoundError: Capsule not found.
            WrennConflictError: Capsule is not running.
            WrennAgentError: Agent error.
            WrennHostUnavailableError: Host agent not reachable.
        """
        assert self._http is not None
        resp = self._http.post(
            f"/v1/capsules/{self.id}/files/remove",
            json={"path": path},
        )
        handle_response(resp)

    async def async_remove(self, path: str) -> None:
        """Async version of ``remove``."""
        assert self._async_http is not None
        resp = await self._async_http.post(
            f"/v1/capsules/{self.id}/files/remove",
            json={"path": path},
        )
        handle_response(resp)

    @contextmanager
    def pty(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> Iterator[PtySession]:
        """Open an interactive PTY session.

        Args:
            cmd: Command to run. Defaults to /bin/bash.
            args: Command arguments.
            cols: Terminal columns. Defaults to 80.
            rows: Terminal rows. Defaults to 24.
            envs: Environment variables.
            cwd: Working directory.

        Returns:
            A PtySession context manager. Use with a ``with`` statement.
        """
        assert self._http is not None
        assert self.id is not None
        with httpx_ws.connect_ws(  # type: ignore[attr-defined]
            f"/v1/capsules/{self.id}/pty", client=self._http
        ) as ws:
            session = PtySession(ws, self.id)
            session._send_start(
                cmd=cmd, args=args, cols=cols, rows=rows, envs=envs, cwd=cwd
            )
            yield session

    @contextmanager
    def pty_connect(self, tag: str) -> Iterator[PtySession]:
        """Reconnect to an existing PTY session.

        Args:
            tag: Session tag from a previous PtySession.

        Returns:
            A PtySession context manager.
        """
        assert self._http is not None
        assert self.id is not None
        with httpx_ws.connect_ws(
            f"/v1/capsules/{self.id}/pty", client=self._http
        ) as ws:
            session = PtySession(ws, self.id)
            session._send_connect(tag)
            yield session

    @asynccontextmanager
    async def async_pty(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> AsyncIterator[AsyncPtySession]:
        """Async version of ``pty``."""
        assert self._async_http is not None
        assert self.id is not None
        async with httpx_ws.aconnect_ws(  # type: ignore[attr-defined, misc]
            f"/v1/capsules/{self.id}/pty", client=self._async_http
        ) as ws:
            session = AsyncPtySession(ws, self.id)
            await session._send_start(
                cmd=cmd, args=args, cols=cols, rows=rows, envs=envs, cwd=cwd
            )
            yield session

    @asynccontextmanager
    async def async_pty_connect(self, tag: str) -> AsyncIterator[AsyncPtySession]:
        """Async version of ``pty_connect``."""
        assert self._async_http is not None
        assert self.id is not None
        async with httpx_ws.aconnect_ws(  # type: ignore[attr-defined, misc]
            f"/v1/capsules/{self.id}/pty", client=self._async_http
        ) as ws:
            session = AsyncPtySession(ws, self.id)
            await session._send_connect(tag)
            yield session

    def ping(self) -> None:
        """Reset the capsule inactivity timer."""
        assert self._http is not None
        resp = self._http.post(f"/v1/capsules/{self.id}/ping")
        resp.raise_for_status()

    async def async_ping(self) -> None:
        """Async version of ``ping``."""
        assert self._async_http is not None
        resp = await self._async_http.post(f"/v1/capsules/{self.id}/ping")
        resp.raise_for_status()

    def pause(self) -> Capsule:
        """Pause the capsule (snapshot and release resources).

        Returns:
            Updated ``Capsule`` with new status.
        """
        assert self._http is not None
        resp = self._http.post(f"/v1/capsules/{self.id}/pause")
        resp.raise_for_status()
        updated = Capsule.model_validate(resp.json())
        self.status = updated.status
        return self

    async def async_pause(self) -> Capsule:
        """Async version of ``pause``."""
        assert self._async_http is not None
        resp = await self._async_http.post(f"/v1/capsules/{self.id}/pause")
        resp.raise_for_status()
        updated = Capsule.model_validate(resp.json())
        self.status = updated.status
        return self

    def resume(self) -> Capsule:
        """Resume a paused capsule from its snapshot.

        Returns:
            Updated ``Capsule`` with new status.
        """
        assert self._http is not None
        resp = self._http.post(f"/v1/capsules/{self.id}/resume")
        resp.raise_for_status()
        updated = Capsule.model_validate(resp.json())
        self.status = updated.status
        return self

    async def async_resume(self) -> Capsule:
        """Async version of ``resume``."""
        assert self._async_http is not None
        resp = await self._async_http.post(f"/v1/capsules/{self.id}/resume")
        resp.raise_for_status()
        updated = Capsule.model_validate(resp.json())
        self.status = updated.status
        return self

    def destroy(self) -> None:
        """Tear down the capsule."""
        assert self._http is not None
        resp = self._http.delete(f"/v1/capsules/{self.id}")
        resp.raise_for_status()

        if self._proxy_client is not None:
            self._proxy_client.close()

    async def async_destroy(self) -> None:
        """Async version of ``destroy``."""
        assert self._async_http is not None
        resp = await self._async_http.delete(f"/v1/capsules/{self.id}")
        resp.raise_for_status()

        if self._async_proxy_client is not None:
            await self._async_proxy_client.aclose()

    def _ensure_kernel(self, jupyter_timeout: float = 30) -> str:
        """Ensure a Jupyter kernel is running, creating one if needed.

        Polls the Jupyter server until it responds, then creates a kernel.

        Args:
            jupyter_timeout: Maximum seconds to wait for Jupyter to become available.

        Returns:
            The kernel ID.

        Raises:
            TimeoutError: If Jupyter doesn't respond within the timeout.
        """
        current_kernel = self._kernel_id
        if current_kernel is not None:
            return current_kernel
        deadline = time.monotonic() + jupyter_timeout
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            try:
                resp = self.http_client.post("/api/kernels")
                if resp.status_code < 500:
                    resp.raise_for_status()
                    data = resp.json()
                    self._kernel_id = data["id"]
                    return str(self._kernel_id)
                last_exc = httpx.HTTPStatusError(
                    f"Jupyter returned {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
            time.sleep(0.5)
        raise TimeoutError(
            f"Jupyter not available within {jupyter_timeout}s: {last_exc}"
        )

    async def _async_ensure_kernel(self, jupyter_timeout: float = 30) -> str:
        """Async version of ``_ensure_kernel``."""
        import asyncio

        current_kernel = self._kernel_id
        if current_kernel is not None:
            return current_kernel

        if self._async_proxy_client is None:
            url = (
                _build_proxy_url(self._base_url, self.id, 8888)
                .replace("ws://", "http://")
                .replace("wss://", "https://")
            )
            self._async_proxy_client = httpx.AsyncClient(
                base_url=url,
                headers=self._proxy_headers(),
            )

        deadline = time.monotonic() + jupyter_timeout
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            try:
                resp = await self._async_proxy_client.post("/api/kernels")
                if resp.status_code < 500:
                    resp.raise_for_status()
                    data = resp.json()
                    self._kernel_id = data["id"]
                    return str(self._kernel_id)
                last_exc = httpx.HTTPStatusError(
                    f"Jupyter returned {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
            await asyncio.sleep(0.5)
        raise TimeoutError(
            f"Jupyter not available within {jupyter_timeout}s: {last_exc}"
        )

    def _jupyter_ws_url(self, kernel_id: str) -> str:
        proxy = _build_proxy_url(self._base_url, self.id, 8888)
        return f"{proxy}/api/kernels/{kernel_id}/channels"

    def _jupyter_execute_request(self, code: str) -> dict:
        msg_id = str(uuid.uuid4())
        return {
            "header": {
                "msg_id": msg_id,
                "msg_type": "execute_request",
                "username": "wrenn-sdk",
                "session": str(uuid.uuid4()),
                "date": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                "version": "5.3",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            "buffers": [],
            "channel": "shell",
            "msg_id": msg_id,
            "msg_type": "execute_request",
        }

    def run_code(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30,
        jupyter_timeout: float = 30,
    ) -> CodeResult:
        """Execute code in a persistent kernel inside the capsule.

        Variables, imports, and function definitions survive across calls.

        Args:
            code: Code string to execute.
            language: Execution backend language. Currently only ``"python"``.
            timeout: Maximum seconds to wait for execution to complete.
            jupyter_timeout: Maximum seconds to wait for Jupyter to become available.

        Returns:
            A ``CodeResult`` with ``.text``, ``.data``, ``.stdout``, ``.stderr``, ``.error``.
        """
        assert self._http is not None
        kernel_id = self._ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = self._jupyter_ws_url(kernel_id)

        msg = self._jupyter_execute_request(code)
        msg_id = msg["msg_id"]

        result = CodeResult()
        deadline = time.monotonic() + timeout

        headers = self._proxy_headers()

        with httpx_ws.connect_ws(ws_url, headers=headers) as ws:  # type: ignore[attr-defined, var-annotated]
            ws.send_text(json.dumps(msg))
            while time.monotonic() < deadline:
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    break
                try:
                    data = ws.receive_json(timeout=time_left)
                except (TimeoutError, Exception):
                    break
                if not data:
                    break
                parent = data.get("parent_header", {}).get("msg_id")
                if parent != msg_id:
                    continue
                msg_type = data.get("msg_type") or data.get("header", {}).get(
                    "msg_type"
                )
                content = data.get("content", {})

                if msg_type == "stream":
                    name = content.get("name", "stdout")
                    if name == "stderr":
                        result.stderr += content.get("text", "")
                    else:
                        result.stdout += content.get("text", "")
                elif msg_type == "execute_result":
                    bundle = content.get("data", {})
                    result.text = bundle.get("text/plain")
                    result.data = bundle
                elif msg_type == "error":
                    traceback = content.get("traceback", [])
                    result.error = "\n".join(traceback)
                elif msg_type == "status" and content.get("execution_state") == "idle":
                    break

        return result

    async def async_run_code(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30,
        jupyter_timeout: float = 30,
    ) -> CodeResult:
        """Async version of ``run_code``."""
        assert self._async_http is not None
        kernel_id = await self._async_ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = self._jupyter_ws_url(kernel_id)

        msg = self._jupyter_execute_request(code)
        msg_id = msg["msg_id"]

        result = CodeResult()
        deadline = time.monotonic() + timeout

        headers = self._proxy_headers()

        async with httpx_ws.aconnect_ws(ws_url, headers=headers) as ws:  # type: ignore[attr-defined, var-annotated]
            await ws.send_text(json.dumps(msg))
            while time.monotonic() < deadline:
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    break

                try:
                    data = await asyncio.wait_for(ws.receive_json(), timeout=time_left)  # type: ignore[misc]
                except (asyncio.TimeoutError, Exception):
                    break

                if not data:
                    break

                parent = data.get("parent_header", {}).get("msg_id")
                if parent != msg_id:
                    continue
                msg_type = data.get("msg_type") or data.get("header", {}).get(
                    "msg_type"
                )
                content = data.get("content", {})

                if msg_type == "stream":
                    name = content.get("name", "stdout")
                    if name == "stderr":
                        result.stderr += content.get("text", "")
                    else:
                        result.stdout += content.get("text", "")
                elif msg_type == "execute_result":
                    bundle = content.get("data", {})
                    result.text = bundle.get("text/plain")
                    result.data = bundle
                elif msg_type == "error":
                    traceback = content.get("traceback", [])
                    result.error = "\n".join(traceback)
                elif msg_type == "status" and content.get("execution_state") == "idle":
                    break

        return result

    def metrics(self, range: str = "10m") -> CapsuleMetrics:
        """Get per-capsule resource metrics.

        Args:
            range: Time range filter (5m, 10m, 1h, 2h, 6h, 12h, 24h).

        Returns:
            ``CapsuleMetrics`` with time-series CPU, memory, and disk data.
        """
        assert self._http is not None
        resp = self._http.get(
            f"/v1/capsules/{self.id}/metrics", params={"range": range}
        )
        data = handle_response(resp)
        return CapsuleMetrics.model_validate(data)

    async def async_metrics(self, range: str = "10m") -> CapsuleMetrics:
        """Async version of ``metrics``."""
        assert self._async_http is not None
        resp = await self._async_http.get(
            f"/v1/capsules/{self.id}/metrics", params={"range": range}
        )
        data = handle_response(resp)
        return CapsuleMetrics.model_validate(data)

    def list_processes(self) -> ProcessListResponse:
        """List all running processes inside the capsule.

        Returns:
            ``ProcessListResponse`` with a list of ``ProcessEntry`` objects.
        """
        assert self._http is not None
        resp = self._http.get(f"/v1/capsules/{self.id}/processes")
        data = handle_response(resp)
        return ProcessListResponse.model_validate(data)

    async def async_list_processes(self) -> ProcessListResponse:
        """Async version of ``list_processes``."""
        assert self._async_http is not None
        resp = await self._async_http.get(f"/v1/capsules/{self.id}/processes")
        data = handle_response(resp)
        return ProcessListResponse.model_validate(data)

    def kill_process(self, selector: str, signal: str = "SIGKILL") -> None:
        """Kill a running process inside the capsule.

        Args:
            selector: Process PID (numeric) or tag (string).
            signal: Signal to send (SIGKILL or SIGTERM).
        """
        assert self._http is not None
        resp = self._http.delete(
            f"/v1/capsules/{self.id}/processes/{selector}",
            params={"signal": signal},
        )
        handle_response(resp)

    async def async_kill_process(self, selector: str, signal: str = "SIGKILL") -> None:
        """Async version of ``kill_process``."""
        assert self._async_http is not None
        resp = await self._async_http.delete(
            f"/v1/capsules/{self.id}/processes/{selector}",
            params={"signal": signal},
        )
        handle_response(resp)

    def connect_process(self, selector: str) -> Iterator[StreamEvent]:
        """Stream output from a background process via WebSocket.

        Args:
            selector: Process PID (numeric) or tag (string).

        Yields:
            ``StreamStartEvent``, ``StreamStdoutEvent``, ``StreamStderrEvent``,
            ``StreamExitEvent``, or ``StreamErrorEvent``.
        """
        assert self._http is not None
        ws: httpx_ws.WebSocketSession
        with httpx_ws.connect_ws(
            f"/v1/capsules/{self.id}/processes/{selector}/stream",
            self._http,
        ) as ws:
            while True:
                try:
                    raw_data: dict = ws.receive_json()
                    event = _parse_stream_event(raw_data)
                    yield event
                    if event.type in ("exit", "error"):
                        break
                except httpx_ws.WebSocketDisconnect:
                    break

    async def async_connect_process(self, selector: str) -> AsyncIterator[StreamEvent]:
        """Async version of ``connect_process``."""
        assert self._async_http is not None
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self.id}/processes/{selector}/stream",
            self._async_http,
        ) as ws:
            try:
                while True:
                    raw_data = await ws.receive_json()
                    event = _parse_stream_event(raw_data)
                    yield event
                    if event.type in ("exit", "error"):
                        break
            except httpx_ws.WebSocketDisconnect:
                pass

    def _cleanup(self) -> None:
        if self._proxy_client is not None:
            try:
                self._proxy_client.close()
            except Exception:
                pass
            self._proxy_client = None

    async def _async_cleanup(self) -> None:
        if self._async_proxy_client is not None:
            try:
                await self._async_proxy_client.aclose()
            except Exception:
                pass
            self._async_proxy_client = None

    def __enter__(self) -> Capsule:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            self.destroy()
        except Exception:
            pass
        self._cleanup()

    async def __aenter__(self) -> Capsule:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            await self.async_destroy()
        except Exception:
            pass
        await self._async_cleanup()


def __getattr__(name: str) -> type:
    if name == "Sandbox":
        warnings.warn(
            "'Sandbox' is deprecated, use 'Capsule' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return Capsule
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
