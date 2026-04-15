import warnings as _warnings

from wrenn.capsule import Capsule  # noqa: F401
from wrenn.commands import (  # noqa: F401
    StreamErrorEvent,
    StreamEvent,
    StreamExitEvent,
    StreamStartEvent,
    StreamStderrEvent,
    StreamStdoutEvent,
)


def __getattr__(name: str) -> type:
    if name == "Sandbox":
        _warnings.warn(
            "'Sandbox' is deprecated, use 'Capsule' instead",
            FutureWarning,
            stacklevel=2,
        )
        return Capsule
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
