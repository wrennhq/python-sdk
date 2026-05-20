"""Shared Jupyter protocol helpers used by both sync and async capsules.

Pure functions only — no I/O, no sync/async coupling.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from wrenn.capsule import _build_proxy_url
from wrenn.code_runner.models import (
    Execution,
    ExecutionError,
    Result,
)


def build_execute_request(code: str) -> dict:
    """Build a Jupyter ``execute_request`` message envelope.

    Returns:
        dict: A fully-formed Jupyter shell-channel message ready to be
        JSON-serialized over the kernel WebSocket. The caller is
        expected to read ``msg["header"]["msg_id"]`` to correlate
        responses.
    """
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


def pick_kernel_id(kernels: list[dict], kernel_name: str) -> str | None:
    """Return the ID of the first kernel matching ``kernel_name``, else ``None``."""
    for k in kernels:
        if k.get("name") == kernel_name:
            return k.get("id")
    return None


def apply_kernel_message(
    data: dict,
    msg_id: str,
    execution: Execution,
    emit_error: Callable[[ExecutionError], None],
    on_result: Callable[[Result], Any] | None,
    on_stdout: Callable[[str], Any] | None,
    on_stderr: Callable[[str], Any] | None,
) -> bool:
    """Apply one Jupyter IOPub message to ``execution``.

    Returns ``True`` when the message marks idle (cell done); the caller
    should stop reading further messages.
    """
    parent = data.get("parent_header", {}).get("msg_id")
    if parent != msg_id:
        return False
    msg_type = data.get("msg_type") or data.get("header", {}).get("msg_type")
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
        emit_error(
            ExecutionError(
                name=content.get("ename", ""),
                value=content.get("evalue", ""),
                traceback="\n".join(content.get("traceback", [])),
            )
        )
    elif msg_type == "status" and content.get("execution_state") == "idle":
        return True
    return False


def validate_language(language: str) -> None:
    if language != "python":
        raise ValueError(
            f"language={language!r} is not supported; only 'python'. "
            "Use the ``kernel=`` constructor argument to target a "
            "non-Python kernelspec."
        )


def build_ws_url(
    base_url: str,
    capsule_id: str,
    kernel_id: str,
    proxy_domain: str | None = None,
) -> str:
    """Build the Jupyter kernel WebSocket URL for the given capsule."""
    proxy = _build_proxy_url(base_url, capsule_id, 8888, proxy_domain)
    return f"{proxy}/api/kernels/{kernel_id}/channels"
