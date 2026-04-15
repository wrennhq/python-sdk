from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

import httpx
import httpx_ws

from wrenn.capsule import Capsule as BaseCapsule
from wrenn.capsule import _build_proxy_url


DEFAULT_TEMPLATE = "code-runner-beta"


@dataclass
class CodeResult:
    """Result from stateful code execution.

    Attributes:
        text: text/plain representation of the result.
        data: rich MIME bundle (e.g. ``{"image/png": "..."}``).
        stdout: accumulated stdout output.
        stderr: accumulated stderr output.
        error: language-specific error/traceback string.
    """

    text: str | None = None
    data: dict[str, str] | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class Capsule(BaseCapsule):
    """Code interpreter capsule with ``run_code`` support.

    Uses ``code-runner-beta`` template by default::

        from wrenn.code_interpreter import Capsule

        capsule = Capsule()
        result = capsule.run_code("print('hello')")
        print(result.stdout)  # "hello\\n"
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

    @classmethod
    def create(
        cls,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Capsule:
        return cls(
            template=template or DEFAULT_TEMPLATE,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout=timeout,
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
            except httpx.HTTPStatusError:
                raise
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
        """Execute code in a persistent Jupyter kernel.

        Variables, imports, and function definitions survive across calls.

        Args:
            code: Code string to execute.
            language: Execution backend language. Currently only ``"python"``.
            timeout: Maximum seconds to wait for execution to complete.
            jupyter_timeout: Maximum seconds to wait for Jupyter to become available.

        Returns:
            A ``CodeResult`` with ``.text``, ``.data``, ``.stdout``, ``.stderr``, ``.error``.
        """
        kernel_id = self._ensure_kernel(jupyter_timeout=jupyter_timeout)
        ws_url = self._jupyter_ws_url(kernel_id)

        msg = self._jupyter_execute_request(code)
        msg_id = msg["msg_id"]

        result = CodeResult()
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

    def __exit__(self, *args) -> None:
        if self._proxy_client is not None:
            try:
                self._proxy_client.close()
            except Exception:
                pass
        super().__exit__(*args)
