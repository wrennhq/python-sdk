"""Deprecated alias for :mod:`wrenn.code_runner`.

Importing from ``wrenn.code_interpreter`` emits a ``FutureWarning``.
Use ``wrenn.code_runner`` instead.
"""

from __future__ import annotations

import warnings as _warnings

warnings_emitted: bool = False


def _warn_once() -> None:
    global warnings_emitted
    if warnings_emitted:
        return
    warnings_emitted = True
    _warnings.warn(
        "'wrenn.code_interpreter' is deprecated, use 'wrenn.code_runner' instead",
        FutureWarning,
        stacklevel=3,
    )


_warn_once()

from wrenn.code_runner.async_capsule import AsyncCapsule  # noqa: E402
from wrenn.code_runner.capsule import Capsule  # noqa: E402
from wrenn.code_runner.models import (  # noqa: E402
    Execution,
    ExecutionError,
    Logs,
    Result,
)

__all__ = [
    "AsyncCapsule",
    "Capsule",
    "Execution",
    "ExecutionError",
    "Logs",
    "Result",
    "Sandbox",
]


def __getattr__(name: str) -> type:
    import sys

    _module = sys.modules[__name__]

    if name == "Sandbox":
        _warnings.warn(
            "'Sandbox' is deprecated, use 'Capsule' instead",
            FutureWarning,
            stacklevel=2,
        )
        setattr(_module, name, Capsule)
        return Capsule
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
