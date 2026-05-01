from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import httpx_ws

from wrenn.async_capsule import AsyncCapsule as BaseAsyncCapsule
from wrenn.capsule import _build_proxy_url
from wrenn.client import AsyncWrennClient
from wrenn.code_interpreter.capsule import DEFAULT_TEMPLATE
from wrenn.code_interpreter.models import (
    Execution,
    ExecutionError,
    Result,
)


class AsyncCapsule(BaseAsyncCapsule):
    """Async code interpreter capsule with ``run_code`` support.

    Uses ``code-runner-beta`` template by default::

        from wrenn.code_interpreter import AsyncCapsule

        capsule = await AsyncCapsule.create()
        result = await capsule.run_code("print('hello')")
    """

    _kernel_id: str | None
    _proxy_client: httpx.AsyncClient | None

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._kernel_id = None
        self._proxy_client = None

    @classmethod
    async def create(
        cls,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        wait: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncCapsule:
        """Create a new async code interpreter capsule.

        Args:
            template (str | None): Template to boot from. Defaults to
                ``"code-runner-beta"``.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout (int | None): Inactivity TTL in seconds before auto-pause.
            wait (bool): Await until the capsule reaches ``running`` status.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            AsyncCapsule: A new async code interpreter capsule instance.
        """
        client = AsyncWrennClient(api_key=api_key, base_url=base_url)
        info = await client.capsules.create(
            template=template or DEFAULT_TEMPLATE,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout_sec=timeout,
        )
        capsule = cls(
            _capsule_id=info.id,
            _client=client,
            _info=info,
        )
        if wait:
            await capsule.wait_ready()
        return capsule

    def _get_proxy_client(self) -> httpx.AsyncClient:
        if self._proxy_client is None:
            url = (
                _build_proxy_url(self._client._base_url, self._id, 8888)
                .replace("ws://", "http://")
                .replace("wss://", "https://")
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
                # Try to reuse an existing kernel
                resp = await client.get("/api/kernels")
                if resp.status_code < 500:
                    resp.raise_for_status()
                    kernels = resp.json()
                    if kernels:
                        self._kernel_id = kernels[0]["id"]
                        return self._kernel_id
                    # No existing kernels, create a new one
                    resp = await client.post("/api/kernels")
                    if resp.status_code < 500:
                        resp.raise_for_status()
                        self._kernel_id = resp.json()["id"]
                        return self._kernel_id
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
        proxy = _build_proxy_url(self._client._base_url, self._id, 8888)
        return f"{proxy}/api/kernels/{kernel_id}/channels"

    @staticmethod
    def _jupyter_execute_request(code: str) -> dict:
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
        kernel_id = await self._ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = self._jupyter_ws_url(kernel_id)

        msg = self._jupyter_execute_request(code)
        msg_id = msg["msg_id"]

        execution = Execution()
        deadline = time.monotonic() + timeout
        headers = {"X-API-Key": self._client._api_key}

        async with httpx_ws.aconnect_ws(ws_url, headers=headers) as ws:  # type: httpx_ws.AsyncWebSocketSession
            await ws.send_text(json.dumps(msg))
            while time.monotonic() < deadline:
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    break
                try:
                    data = await asyncio.wait_for(ws.receive_json(), timeout=time_left)
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
                    err = ExecutionError(
                        name=content.get("ename", ""),
                        value=content.get("evalue", ""),
                        traceback="\n".join(content.get("traceback", [])),
                    )
                    execution.error = err
                    if on_error is not None:
                        on_error(err)
                elif msg_type == "status" and content.get("execution_state") == "idle":
                    break

        return execution

    async def __aexit__(self, *args) -> None:
        if self._proxy_client is not None:
            try:
                await self._proxy_client.aclose()
            except Exception:
                pass
        await super().__aexit__(*args)
