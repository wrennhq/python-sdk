"""Shared Jupyter protocol helpers used by both sync and async capsules.

Pure functions only — no I/O, no sync/async coupling.
"""

from __future__ import annotations

import time
import uuid

from wrenn.capsule import _build_proxy_url


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


def build_ws_url(base_url: str, capsule_id: str, kernel_id: str) -> str:
    """Build the Jupyter kernel WebSocket URL for the given capsule."""
    proxy = _build_proxy_url(base_url, capsule_id, 8888)
    return f"{proxy}/api/kernels/{kernel_id}/channels"
