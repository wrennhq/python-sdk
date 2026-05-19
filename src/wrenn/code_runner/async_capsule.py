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
from wrenn.code_runner._protocol import build_execute_request, build_ws_url
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

    def __init__(self, *, kernel: str | None = None, **kwargs) -> None:
        # Set attrs before super().__init__ so __del__ never sees a
        # half-constructed instance.
        self._kernel_id = None
        self._kernel_name = kernel or DEFAULT_KERNEL
        self._proxy_client = None
        super().__init__(**kwargs)

    async def close(self) -> None:
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
        info = await client.capsules.create(
            template=template or DEFAULT_TEMPLATE,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout_sec=timeout,
        )
        capsule = cls(
            kernel=kernel,
            _capsule_id=info.id,
            _client=client,
            _info=info,
        )
        if wait:
            await capsule.wait_ready()
        return capsule

    def _get_proxy_client(self) -> httpx.AsyncClient:
        if self._proxy_client is None:
            url = _build_http_proxy_url(self._client._base_url, self._id, 8888)
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
                    kernels = resp.json()
                    for k in kernels:
                        if k.get("name") == self._kernel_name:
                            self._kernel_id = k["id"]
                            return self._kernel_id
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

        Args:
            code: Code string to execute.
            language: Execution backend language. Currently only ``"python"``.
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
        if language != "python":
            raise ValueError(
                f"language={language!r} is not supported; only 'python'. "
                "Use the ``kernel=`` constructor argument to target a "
                "non-Python kernelspec."
            )
        kernel_id = await self._ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = build_ws_url(self._client._base_url, self._id, kernel_id)

        msg = build_execute_request(code)
        msg_id = msg["header"]["msg_id"]

        execution = Execution()
        deadline = time.monotonic() + timeout
        headers = {"X-API-Key": self._client._api_key}
        saw_idle = False

        def _emit_error(err: ExecutionError) -> None:
            execution.error = err
            if on_error is not None:
                on_error(err)

        async with httpx_ws.aconnect_ws(ws_url, headers=headers) as ws:  # type: httpx_ws.AsyncWebSocketSession
            await ws.send_text(json.dumps(msg))
            while True:
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    break
                try:
                    data = await asyncio.wait_for(ws.receive_json(), timeout=time_left)
                except (asyncio.TimeoutError, TimeoutError):
                    break
                except (
                    httpx_ws.WebSocketDisconnect,
                    httpx_ws.WebSocketNetworkError,
                ) as exc:
                    execution.timed_out = True
                    _emit_error(
                        ExecutionError(
                            name="Disconnected",
                            value=f"kernel WebSocket closed: {exc}",
                        )
                    )
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
                    text = content.get("text", "")
                    name = content.get("name", "stdout")
                    if name == "stderr":
                        execution.logs.stderr.append(text)
                        if on_stderr is not None:
                            on_stderr(text)
                    else:
                        execution.logs.stdout.append(text)
                        if on_stdout is not None:
                            on_stdout(text)
                elif msg_type in ("execute_result", "display_data"):
                    bundle = content.get("data", {})
                    is_main = msg_type == "execute_result"
                    result = Result.from_bundle(bundle, is_main_result=is_main)
                    execution.results.append(result)
                    if is_main:
                        execution.execution_count = content.get("execution_count")
                    if on_result is not None:
                        on_result(result)
                elif msg_type == "error":
                    _emit_error(
                        ExecutionError(
                            name=content.get("ename", ""),
                            value=content.get("evalue", ""),
                            traceback="\n".join(content.get("traceback", [])),
                        )
                    )
                elif msg_type == "status" and content.get("execution_state") == "idle":
                    saw_idle = True
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
