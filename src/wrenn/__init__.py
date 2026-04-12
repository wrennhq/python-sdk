from wrenn.capsule import (
    Capsule,
    CodeResult,
    ExecResult,
    StreamErrorEvent,
    StreamEvent,
    StreamExitEvent,
    StreamStartEvent,
    StreamStderrEvent,
    StreamStdoutEvent,
)
from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.exceptions import (
    WrennAgentError,
    WrennAuthenticationError,
    WrennConflictError,
    WrennError,
    WrennForbiddenError,
    WrennHostHasCapsulesError,
    WrennHostUnavailableError,
    WrennInternalError,
    WrennNotFoundError,
    WrennValidationError,
)
from wrenn.models import FileEntry
from wrenn.pty import AsyncPtySession, PtyEvent, PtyEventType, PtySession

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AsyncPtySession",
    "AsyncWrennClient",
    "Capsule",
    "CodeResult",
    "ExecResult",
    "FileEntry",
    "PtyEvent",
    "PtyEventType",
    "PtySession",
    "Sandbox",
    "StreamErrorEvent",
    "StreamEvent",
    "StreamExitEvent",
    "StreamStartEvent",
    "StreamStderrEvent",
    "StreamStdoutEvent",
    "WrennAgentError",
    "WrennAuthenticationError",
    "WrennClient",
    "WrennConflictError",
    "WrennError",
    "WrennForbiddenError",
    "WrennHostHasCapsulesError",
    "WrennHostHasSandboxesError",
    "WrennHostUnavailableError",
    "WrennInternalError",
    "WrennNotFoundError",
    "WrennValidationError",
]


def __getattr__(name: str) -> type:
    if name == "Sandbox":
        import warnings

        warnings.warn(
            "'Sandbox' is deprecated, use 'Capsule' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return Capsule
    if name == "WrennHostHasSandboxesError":
        import warnings

        warnings.warn(
            "'WrennHostHasSandboxesError' is deprecated, use 'WrennHostHasCapsulesError' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return WrennHostHasCapsulesError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
