from wrenn._git import (
    AsyncGit,
    FileStatus,
    Git,
    GitAuthError,
    GitBranch,
    GitCommandError,
    GitError,
    GitStatus,
)
from wrenn.async_capsule import AsyncCapsule
from wrenn.capsule import Capsule
from wrenn.client import AsyncWrennClient, WrennClient
from wrenn.commands import (
    CommandHandle,
    CommandResult,
    ProcessInfo,
    StreamErrorEvent,
    StreamEvent,
    StreamExitEvent,
    StreamStartEvent,
    StreamStderrEvent,
    StreamStdoutEvent,
)
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
    "AsyncCapsule",
    "AsyncGit",
    "AsyncPtySession",
    "AsyncWrennClient",
    "Capsule",
    "CommandHandle",
    "CommandResult",
    "FileEntry",
    "FileStatus",
    "Git",
    "GitAuthError",
    "GitBranch",
    "GitCommandError",
    "GitError",
    "GitStatus",
    "ProcessInfo",
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
    if name == "WrennHostHasSandboxesError":
        warnings.warn(
            "'WrennHostHasSandboxesError' is deprecated, use 'WrennHostHasCapsulesError' instead",
            FutureWarning,
            stacklevel=2,
        )
        setattr(_module, name, WrennHostHasCapsulesError)
        return WrennHostHasCapsulesError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
