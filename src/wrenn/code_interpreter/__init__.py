from wrenn.code_interpreter.async_capsule import AsyncCapsule
from wrenn.code_interpreter.capsule import Capsule, CodeResult

__all__ = [
    "AsyncCapsule",
    "Capsule",
    "CodeResult",
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
