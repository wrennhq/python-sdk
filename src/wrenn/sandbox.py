import warnings as _warnings

from wrenn.capsule import (  # noqa: F401
    CodeResult,
    ExecResult,
    StreamErrorEvent,
    StreamEvent,
    StreamExitEvent,
    StreamStartEvent,
    StreamStderrEvent,
    StreamStdoutEvent,
    _build_proxy_url,
    _parse_stream_event,
)
from wrenn.capsule import Capsule


def __getattr__(name: str) -> type:
    if name == "Sandbox":
        _warnings.warn(
            "'Sandbox' is deprecated, use 'Capsule' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return Capsule
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
