from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import httpx_ws

from wrenn.exceptions import WrennAuthenticationError
from wrenn.models import ExecResponse, Status
from wrenn.models import Sandbox as SandboxModel


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


def _build_proxy_url(base_url: str, sandbox_id: str | None, port: int) -> str:
    parsed = httpx.URL(base_url)
    host = parsed.host
    if parsed.port:
        host = f"{host}:{parsed.port}"
    scheme = "ws" if parsed.scheme == "http" else "wss"
    return f"{scheme}://{port}-{sandbox_id}.{host}"


class Sandbox(SandboxModel):
    """Developer-facing sandbox interface wrapping the generated Sandbox model.

    Provides data-plane methods (exec, file I/O, lifecycle), sandbox proxy
    helpers, and context-manager support for automatic cleanup.
    """

    _http: httpx.Client | None
    _async_http: httpx.AsyncClient | None
    _base_url: str
    _api_key: str | None
    _token: str | None
    _proxy_client: httpx.Client | None
    _async_proxy_client: httpx.AsyncClient | None
    _kernel_id: str | None
    _jupyter_ws: Any
    _async_jupyter_ws: Any

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

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise WrennAuthenticationError(
                code="unauthorized",
                message="Proxy requires an API key. JWT-only clients cannot use proxy routes.",
                status_code=401,
            )
        return self._api_key

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
        """Construct the proxy URL for a port inside this sandbox.

        Args:
            port: Port number of the service running inside the sandbox.

        Returns:
            A URL string like ``http://8888-cl-abc123.api.wrenn.dev``.

        Raises:
            WrennAuthenticationError: If the client was constructed with JWT only.
        """
        self._require_api_key()
        return _build_proxy_url(self._base_url, self.id, port)

    @property
    def http_client(self) -> httpx.Client:
        """A pre-configured ``httpx.Client`` targeting the sandbox proxy on port 8888.

        The client has the ``X-API-Key`` header set and ``base_url`` pointing to
        the proxy URL for port 8888.  Closed automatically when the sandbox exits.

        Raises:
            WrennAuthenticationError: If the client was constructed with JWT only.
        """
        self._require_api_key()
        if self._proxy_client is None:
            url = (
                _build_proxy_url(self._base_url, self.id, 8888)
                .replace("ws://", "http://")
                .replace("wss://", "https://")
            )
            self._proxy_client = httpx.Client(
                base_url=url,
                headers={"X-API-Key": self._api_key},  # type: ignore[dict-item, arg-type]
            )
        return self._proxy_client

    def wait_ready(self, timeout: float = 30, interval: float = 0.5) -> None:
        """Block until the sandbox status is ``running``.

        Args:
            timeout: Maximum seconds to wait.
            interval: Seconds between polls.

        Raises:
            TimeoutError: If the sandbox does not become ready in time.
        """
        assert self._http is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = self._http.get(f"/v1/sandboxes/{self.id}")
            data = resp.json()
            status = data.get("status")
            if status == Status.running:
                self.status = Status.running
                return
            if status in (Status.error, Status.stopped):
                raise RuntimeError(f"Sandbox entered {status} state while waiting")
            time.sleep(interval)
        raise TimeoutError(f"Sandbox {self.id} did not become ready within {timeout}s")

    async def async_wait_ready(
        self, timeout: float = 30, interval: float = 0.5
    ) -> None:
        """Async version of ``wait_ready``."""
        assert self._async_http is not None
        import asyncio

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = await self._async_http.get(f"/v1/sandboxes/{self.id}")
            data = resp.json()
            status = data.get("status")
            if status == Status.running:
                self.status = Status.running
                return
            if status in (Status.error, Status.stopped):
                raise RuntimeError(f"Sandbox entered {status} state while waiting")
            await asyncio.sleep(interval)
        raise TimeoutError(f"Sandbox {self.id} did not become ready within {timeout}s")

    def exec(
        self,
        cmd: str,
        args: list[str] | None = None,
        timeout_sec: int | None = 30,
    ) -> ExecResult:
        """Execute a command synchronously inside the sandbox.

        Args:
            cmd: Command to run.
            args: Optional positional arguments.
            timeout_sec: Execution timeout in seconds.

        Returns:
            An ``ExecResult`` with ``stdout``, ``stderr``, ``exit_code``, ``duration_ms``.
        """
        assert self._http is not None
        payload: dict = {"cmd": cmd}
        if args is not None:
            payload["args"] = args
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        resp = self._http.post(f"/v1/sandboxes/{self.id}/exec", json=payload)
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
    ) -> ExecResult:
        """Async version of ``exec``."""
        assert self._async_http is not None
        payload: dict = {"cmd": cmd}
        if args is not None:
            payload["args"] = args
        if timeout_sec is not None:
            payload["timeout_sec"] = timeout_sec
        resp = await self._async_http.post(
            f"/v1/sandboxes/{self.id}/exec", json=payload
        )
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
        with httpx_ws.ws_connect(  # type: ignore[attr-defined]
            f"/v1/sandboxes/{self.id}/exec/stream",
            self._http,
        ) as ws:
            start_msg: dict = {"type": "start", "cmd": cmd}
            if args:
                start_msg["args"] = args
            ws.send(json.dumps(start_msg))
            for raw_msg in ws:
                event = _parse_stream_event(json.loads(raw_msg))
                yield event
                if event.type in ("exit", "error"):
                    break

    async def async_exec_stream(
        self, cmd: str, args: list[str] | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Async version of ``exec_stream``."""
        assert self._async_http is not None
        async with httpx_ws.aconnect_ws(  # type: ignore[attr-defined, var-annotated]
            f"/v1/sandboxes/{self.id}/exec/stream", self._async_http
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
        """Upload a small file to the sandbox.

        Args:
            path: Absolute destination path inside the sandbox.
            data: File contents as bytes.
        """
        assert self._http is not None
        original_ct = self._http.headers.pop("Content-Type", None)
        try:
            resp = self._http.post(
                f"/v1/sandboxes/{self.id}/files/write",
                files={"file": ("upload", data)},
                data={"path": path},
            )
        finally:
            if original_ct is not None:
                self._http.headers["content-type"] = original_ct

        resp.raise_for_status()

    async def async_upload(self, path: str, data: bytes) -> None:
        """Async version of ``upload``."""
        assert self._async_http is not None
        original_ct = self._async_http.headers.pop("Content-Type", None)
        try:
            resp = await self._async_http.post(
                f"/v1/sandboxes/{self.id}/files/write",
                files={"file": ("upload", data)},
                data={"path": path},
            )
        finally:
            if original_ct is not None:
                self._async_http.headers["Content-Type"] = original_ct

        resp.raise_for_status()

    def download(self, path: str) -> bytes:
        """Download a small file from the sandbox.

        Args:
            path: Absolute file path inside the sandbox.

        Returns:
            File contents as bytes.
        """
        assert self._http is not None
        resp = self._http.post(
            f"/v1/sandboxes/{self.id}/files/read",
            json={"path": path},
        )
        resp.raise_for_status()
        return resp.content

    async def async_download(self, path: str) -> bytes:
        """Async version of ``download``."""
        assert self._async_http is not None
        resp = await self._async_http.post(
            f"/v1/sandboxes/{self.id}/files/read",
            json={"path": path},
        )
        resp.raise_for_status()
        return resp.content

    def stream_upload(self, path: str, stream: Iterator[bytes]) -> None:
        """Streaming upload for large files.

        Args:
            path: Absolute destination path inside the sandbox.
            stream: An iterator yielding byte chunks.
        """
        assert self._http is not None

        def _gen() -> Iterator[bytes]:
            yield from stream

        original_ct = self._http.headers.pop("Content-Type", None)
        try:
            resp = self._http.post(
                f"/v1/sandboxes/{self.id}/files/stream/write",
                files={"file": ("upload", _gen())},  # type: ignore[dict-item]
                data={"path": path},
            )
        finally:
            if original_ct is not None:
                self._http.headers["Content-Type"] = original_ct

        resp.raise_for_status()

    async def async_stream_upload(
        self, path: str, stream: AsyncIterator[bytes]
    ) -> None:
        """Async version of ``stream_upload``."""
        assert self._async_http is not None

        async def _gen() -> AsyncIterator[bytes]:
            async for chunk in stream:
                yield chunk

        original_ct = self._async_http.headers.pop("Content-Type", None)
        try:
            resp = await self._async_http.post(
                f"/v1/sandboxes/{self.id}/files/stream/write",
                files={"file": ("upload", _gen())},  # type: ignore[dict-item]
                data={"path": path},
            )
        finally:
            if original_ct is not None:
                self._async_http.headers["Content-Type"] = original_ct

        resp.raise_for_status()

    def stream_download(self, path: str) -> Iterator[bytes]:
        """Streaming download for large files.

        Args:
            path: Absolute file path inside the sandbox.

        Yields:
            Byte chunks.
        """
        assert self._http is not None
        with self._http.stream(
            "POST",
            f"/v1/sandboxes/{self.id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            yield from resp.iter_bytes()

    async def async_stream_download(self, path: str) -> AsyncIterator[bytes]:
        """Async version of ``stream_download``."""
        assert self._async_http is not None
        async with self._async_http.stream(
            "POST",
            f"/v1/sandboxes/{self.id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk

    def ping(self) -> None:
        """Reset the sandbox inactivity timer."""
        assert self._http is not None
        resp = self._http.post(f"/v1/sandboxes/{self.id}/ping")
        resp.raise_for_status()

    async def async_ping(self) -> None:
        """Async version of ``ping``."""
        assert self._async_http is not None
        resp = await self._async_http.post(f"/v1/sandboxes/{self.id}/ping")
        resp.raise_for_status()

    def pause(self) -> Sandbox:
        """Pause the sandbox (snapshot and release resources).

        Returns:
            Updated ``Sandbox`` with new status.
        """
        assert self._http is not None
        resp = self._http.post(f"/v1/sandboxes/{self.id}/pause")
        resp.raise_for_status()
        updated = Sandbox.model_validate(resp.json())
        self.status = updated.status
        return self

    async def async_pause(self) -> Sandbox:
        """Async version of ``pause``."""
        assert self._async_http is not None
        resp = await self._async_http.post(f"/v1/sandboxes/{self.id}/pause")
        resp.raise_for_status()
        updated = Sandbox.model_validate(resp.json())
        self.status = updated.status
        return self

    def resume(self) -> Sandbox:
        """Resume a paused sandbox from its snapshot.

        Returns:
            Updated ``Sandbox`` with new status.
        """
        assert self._http is not None
        resp = self._http.post(f"/v1/sandboxes/{self.id}/resume")
        resp.raise_for_status()
        updated = Sandbox.model_validate(resp.json())
        self.status = updated.status
        return self

    async def async_resume(self) -> Sandbox:
        """Async version of ``resume``."""
        assert self._async_http is not None
        resp = await self._async_http.post(f"/v1/sandboxes/{self.id}/resume")
        resp.raise_for_status()
        updated = Sandbox.model_validate(resp.json())
        self.status = updated.status
        return self

    def destroy(self) -> None:
        """Tear down the sandbox."""
        assert self._http is not None
        resp = self._http.delete(f"/v1/sandboxes/{self.id}")
        resp.raise_for_status()

    async def async_destroy(self) -> None:
        """Async version of ``destroy``."""
        assert self._async_http is not None
        resp = await self._async_http.delete(f"/v1/sandboxes/{self.id}")
        resp.raise_for_status()

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
            except (httpx.HTTPStatusError, WrennAuthenticationError):
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

        self._require_api_key()
        if self._async_proxy_client is None:
            url = (
                _build_proxy_url(self._base_url, self.id, 8888)
                .replace("ws://", "http://")
                .replace("wss://", "https://")
            )
            self._async_proxy_client = httpx.AsyncClient(
                base_url=url,
                headers={"X-API-Key": self._api_key},  # type: ignore[dict-item, arg-type]
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
        """Execute code in a persistent kernel inside the sandbox.

        Variables, imports, and function definitions survive across calls.

        Args:
            code: Code string to execute.
            language: Execution backend language. Currently only ``"python"``.
            timeout: Maximum seconds to wait for execution to complete.
            jupyter_timeout: Maximum seconds to wait for Jupyter to become available.

        Returns:
            A ``CodeResult`` with ``.text``, ``.data``, ``.stdout``, ``.stderr``, ``.error``.

        Raises:
            WrennAuthenticationError: If the client was constructed with JWT only.
        """
        assert self._http is not None
        kernel_id = self._ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = self._jupyter_ws_url(kernel_id)
        api_key = self._require_api_key()

        msg = self._jupyter_execute_request(code)
        msg_id = msg["msg_id"]

        result = CodeResult()
        deadline = time.monotonic() + timeout

        headers = {"X-API-Key": api_key}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

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
        api_key = self._require_api_key()

        msg = self._jupyter_execute_request(code)
        msg_id = msg["msg_id"]

        result = CodeResult()
        deadline = time.monotonic() + timeout

        headers = {"X-API-Key": api_key}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

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

    def __enter__(self) -> Sandbox:
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

    async def __aenter__(self) -> Sandbox:
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
