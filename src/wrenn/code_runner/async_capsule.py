from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

import httpx
import httpx_ws

from wrenn.async_capsule import AsyncCapsule as BaseAsyncCapsule
from wrenn.capsule import _build_http_proxy_url
from wrenn.client import AsyncWrennClient
from wrenn.code_runner._protocol import (
    apply_kernel_message,
    build_execute_request,
    build_ws_url,
    pick_kernel_id,
    validate_language,
)
from wrenn.code_runner.capsule import DEFAULT_KERNEL, DEFAULT_TEMPLATE
from wrenn.code_runner.models import (
    Execution,
    ExecutionError,
    Result,
)


class AsyncCapsule(BaseAsyncCapsule):
    """Async code runner capsule with ``run_code`` support.

    Uses ``code-runner-beta`` template and the ``wrenn`` Jupyter
    kernelspec by default::

        from wrenn.code_runner import AsyncCapsule

        capsule = await AsyncCapsule.create()
        result = await capsule.run_code("print('hello')")
    """

    _kernel_id: str | None
    _kernel_name: str
    _proxy_client: httpx.AsyncClient | None
    _ws: httpx_ws.AsyncWebSocketSession | None
    _ws_cm: Any

    def __init__(self, *, kernel: str | None = None, **kwargs) -> None:
        # Set attrs before super().__init__ so __del__ never sees a
        # half-constructed instance.
        self._kernel_id = None
        self._kernel_name = kernel or DEFAULT_KERNEL
        self._proxy_client = None
        self._ws = None
        self._ws_cm = None
        super().__init__(**kwargs)

    async def _close_ws(self) -> None:
        cm = getattr(self, "_ws_cm", None)
        if cm is not None:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._ws = None
        self._ws_cm = None

    async def _get_ws(self, kernel_id: str) -> httpx_ws.AsyncWebSocketSession:
        if self._ws is not None:
            return self._ws
        ws_url = build_ws_url(
            self._client._base_url,
            self._id,
            kernel_id,
            self._client._proxy_domain,
        )
        headers = {"X-API-Key": self._client._api_key}
        cm: Any = httpx_ws.aconnect_ws(ws_url, headers=headers)
        try:
            ws = await cm.__aenter__()
        except BaseException:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
            raise
        self._ws_cm = cm
        self._ws = ws
        return ws

    async def close(self) -> None:
        await self._close_ws()
        proxy = getattr(self, "_proxy_client", None)
        if proxy is not None:
            try:
                await proxy.aclose()
            except Exception:
                pass
            self._proxy_client = None

    def __del__(self) -> None:
        # Async client cannot be safely closed from __del__; just drop the
        # reference and let httpx warn if the connection was never closed.
        # Users should call ``await close()`` or use ``async with``.
        self._proxy_client = None
        self._ws = None
        self._ws_cm = None

    async def _instance_destroy(self, wait: bool = False) -> None:
        # Release WS + proxy client before destroying the capsule.
        await self.close()
        await super()._instance_destroy(wait=wait)

    @classmethod
    async def create(
        cls,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        kernel: str | None = None,
        wait: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncCapsule:
        """Create a new async code runner capsule.

        Args:
            template (str | None): Template to boot from. Defaults to
                ``"code-runner-beta"``.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout (int | None): Inactivity TTL in seconds before auto-pause.
            kernel (str | None): Jupyter kernelspec name. Defaults to
                ``"wrenn"``.
            wait (bool): Await until the capsule reaches ``running`` status.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            AsyncCapsule: A new async code runner capsule instance.
        """
        client = AsyncWrennClient(api_key=api_key, base_url=base_url)
        try:
            info = await client.capsules.create(
                template=template or DEFAULT_TEMPLATE,
                vcpus=vcpus,
                memory_mb=memory_mb,
                timeout_sec=timeout,
            )
            if info.id is None:
                raise RuntimeError("API returned a capsule without an ID")
            capsule = cls(
                kernel=kernel,
                _capsule_id=info.id,
                _client=client,
                _info=info,
            )
            if wait:
                await capsule.wait_ready()
            return capsule
        except BaseException:
            await client.aclose()
            raise

    def _get_proxy_client(self) -> httpx.AsyncClient:
        if self._proxy_client is None:
            url = _build_http_proxy_url(
                self._client._base_url,
                self._id,
                8888,
                self._client._proxy_domain,
            )
            self._proxy_client = httpx.AsyncClient(
                base_url=url,
                headers={"X-API-Key": self._client._api_key},
            )
        return self._proxy_client

    async def _ensure_kernel(self, jupyter_timeout: float = 30) -> str:
        if self._kernel_id is not None:
            return self._kernel_id

        client = self._get_proxy_client()
        deadline = time.monotonic() + jupyter_timeout
        last_exc: Exception | None = None

        while time.monotonic() < deadline:
            try:
                resp = await client.get("/api/kernels")
                if resp.status_code < 500:
                    resp.raise_for_status()
                    matched = pick_kernel_id(resp.json(), self._kernel_name)
                    if matched is not None:
                        self._kernel_id = matched
                        return matched
                    resp = await client.post(
                        "/api/kernels",
                        json={"name": self._kernel_name},
                    )
                    if resp.status_code < 500:
                        resp.raise_for_status()
                        self._kernel_id = resp.json()["id"]
                        return self._kernel_id
                last_exc = httpx.HTTPStatusError(
                    f"Jupyter returned {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise
                last_exc = exc
            except Exception as exc:
                last_exc = exc
            await asyncio.sleep(0.5)

        raise TimeoutError(
            f"Jupyter not available within {jupyter_timeout}s: {last_exc}"
        )

    async def run_code(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30,
        jupyter_timeout: float = 30,
        on_result: Callable[[Result], Any] | None = None,
        on_stdout: Callable[[str], Any] | None = None,
        on_stderr: Callable[[str], Any] | None = None,
        on_error: Callable[[ExecutionError], Any] | None = None,
    ) -> Execution:
        """Execute code in a persistent Jupyter kernel (async).

        Variables, imports, and function definitions survive across calls.

        Args:
            code: Code string to execute.
            language: Execution backend language. Currently only ``"python"``
                is supported; passing anything else raises ``ValueError``.
                To target a non-Python kernel, set ``kernel=`` on the
                capsule constructor.
            timeout: Maximum seconds to wait for execution to complete.
            jupyter_timeout: Maximum seconds to wait for Jupyter to become
                available.
            on_result: Called for each rich output (charts, images, expression
                values).
            on_stdout: Called for each stdout chunk.
            on_stderr: Called for each stderr chunk.
            on_error: Called when the cell raises an exception.

        Returns:
            An :class:`Execution` with ``.results``, ``.logs``, ``.error``,
            and a convenience ``.text`` property.
        """
        validate_language(language)
        kernel_id = await self._ensure_kernel(jupyter_timeout=jupyter_timeout)

        msg = build_execute_request(code)
        msg_id = msg["header"]["msg_id"]

        execution = Execution()
        deadline = time.monotonic() + timeout
        saw_idle = False

        def _emit_error(err: ExecutionError) -> None:
            execution.error = err
            if on_error is not None:
                on_error(err)

        reconnect_attempts = 1
        sent = False
        while True:
            try:
                ws = await self._get_ws(kernel_id)
                if not sent:
                    await ws.send_text(json.dumps(msg))
                    sent = True
                while True:
                    time_left = deadline - time.monotonic()
                    if time_left <= 0:
                        break
                    data = await asyncio.wait_for(ws.receive_json(), timeout=time_left)
                    if not data:
                        break
                    if apply_kernel_message(
                        data,
                        msg_id,
                        execution,
                        _emit_error,
                        on_result,
                        on_stdout,
                        on_stderr,
                    ):
                        saw_idle = True
                        break
                break
            except TimeoutError:
                break
            except (
                httpx_ws.WebSocketDisconnect,
                httpx_ws.WebSocketNetworkError,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as exc:
                await self._close_ws()
                if reconnect_attempts > 0 and not sent:
                    reconnect_attempts -= 1
                    continue
                _emit_error(
                    ExecutionError(
                        name="Disconnected",
                        value=f"kernel WebSocket closed: {exc}",
                    )
                )
                execution.timed_out = True
                break

        if not saw_idle and execution.error is None:
            execution.timed_out = True
            _emit_error(
                ExecutionError(
                    name="Timeout",
                    value=f"run_code exceeded {timeout}s",
                )
            )

        return execution

    async def __aexit__(self, *args) -> None:
        await self.close()
        await super().__aexit__(*args)
