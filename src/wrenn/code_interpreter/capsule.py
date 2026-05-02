from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import httpx_ws

from wrenn.capsule import Capsule as BaseCapsule
from wrenn.capsule import _build_proxy_url
from wrenn.code_interpreter.models import (
    Execution,
    ExecutionError,
    Result,
)

DEFAULT_TEMPLATE = "code-runner-beta"


class Capsule(BaseCapsule):
    """Code interpreter capsule with ``run_code`` support.

    Uses ``code-runner-beta`` template by default::

        from wrenn.code_interpreter import Capsule

        capsule = Capsule()
        result = capsule.run_code("print('hello')")
        print(result.logs.stdout)  # ["hello\\n"]
    """

    _kernel_id: str | None
    _proxy_client: httpx.Client | None

    def __init__(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ) -> None:
        """Create a code interpreter capsule.

        Args:
            template (str | None): Template to boot from. Defaults to
                ``"code-runner-beta"``.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout (int | None): Inactivity TTL in seconds before auto-pause.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.
        """
        super().__init__(
            template=template or DEFAULT_TEMPLATE,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout=timeout,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
        self._kernel_id = None
        self._proxy_client = None

    def close(self) -> None:
        if self._proxy_client is not None:
            try:
                self._proxy_client.close()
            except Exception:
                pass
            self._proxy_client = None

    def __del__(self) -> None:
        self.close()

    @classmethod
    def create(
        cls,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        wait: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Capsule:
        """Create a new code interpreter capsule.

        Args:
            template (str | None): Template to boot from. Defaults to
                ``"code-runner-beta"``.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout (int | None): Inactivity TTL in seconds before auto-pause.
            wait (bool): Block until the capsule reaches ``running`` status.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            Capsule: A new code interpreter capsule instance.
        """
        return cls(
            template=template or DEFAULT_TEMPLATE,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout=timeout,
            wait=wait,
            api_key=api_key,
            base_url=base_url,
        )

    def _get_proxy_client(self) -> httpx.Client:
        if self._proxy_client is None:
            url = (
                _build_proxy_url(self._client._base_url, self._id, 8888)
                .replace("ws://", "http://")
                .replace("wss://", "https://")
            )
            self._proxy_client = httpx.Client(
                base_url=url,
                headers={"X-API-Key": self._client._api_key},
            )
        return self._proxy_client

    def _ensure_kernel(self, jupyter_timeout: float = 30) -> str:
        if self._kernel_id is not None:
            return self._kernel_id

        client = self._get_proxy_client()
        deadline = time.monotonic() + jupyter_timeout
        last_exc: Exception | None = None

        while time.monotonic() < deadline:
            try:
                # Try to reuse an existing kernel
                resp = client.get("/api/kernels")
                if resp.status_code < 500:
                    resp.raise_for_status()
                    kernels = resp.json()
                    if kernels:
                        self._kernel_id = kernels[0]["id"]
                        return self._kernel_id
                    # No existing kernels, create a new one
                    resp = client.post("/api/kernels")
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
            time.sleep(0.5)

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
        }

    def run_code(
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
        """Execute code in a persistent Jupyter kernel.

        Variables, imports, and function definitions survive across calls.

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
        kernel_id = self._ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = self._jupyter_ws_url(kernel_id)

        msg = self._jupyter_execute_request(code)
        msg_id = msg["header"]["msg_id"]

        execution = Execution()
        deadline = time.monotonic() + timeout
        headers = {"X-API-Key": self._client._api_key}

        with httpx_ws.connect_ws(ws_url, headers=headers) as ws:
            ws.send_text(json.dumps(msg))
            while time.monotonic() < deadline:
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    break
                try:
                    data = ws.receive_json(timeout=time_left)
                except Exception:
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

    def __exit__(self, *args) -> None:
        if self._proxy_client is not None:
            try:
                self._proxy_client.close()
            except Exception:
                pass
        super().__exit__(*args)
