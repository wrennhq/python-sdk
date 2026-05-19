"""Code runner — execute code in persistent Jupyter kernels.

Uses the ``code-runner-beta`` template and the ``wrenn`` Jupyter
kernelspec by default.

Example::

    from wrenn.code_runner import Capsule

    with Capsule(wait=True) as capsule:
        result = capsule.run_code("print('hello')")
        print(result.logs.stdout)
"""

from wrenn.code_runner.async_capsule import AsyncCapsule
from wrenn.code_runner.capsule import DEFAULT_KERNEL, DEFAULT_TEMPLATE, Capsule
from wrenn.code_runner.models import (
    Execution,
    ExecutionError,
    Logs,
    Result,
)

__all__ = [
    "AsyncCapsule",
    "Capsule",
    "DEFAULT_KERNEL",
    "DEFAULT_TEMPLATE",
    "Execution",
    "ExecutionError",
    "Logs",
    "Result",
    "Sandbox",
]


def __getattr__(name: str) -> type:
    import sys
    import warnings

    _module = sys.modules[__name__]

    if name == "Sandbox":
        warnings.warn(
            "'Sandbox' is deprecated, use 'Capsule' instead",
            FutureWarning,
            stacklevel=2,
        )
        setattr(_module, name, Capsule)
        return Capsule
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
