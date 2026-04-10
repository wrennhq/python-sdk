from __future__ import annotations


class WrennError(Exception):
    """Base exception for all Wrenn SDK errors."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class WrennValidationError(WrennError):
    """400 — Invalid request parameters."""


class WrennAuthenticationError(WrennError):
    """401 — Invalid or missing authentication."""


class WrennForbiddenError(WrennError):
    """403 — Authenticated but not authorized."""


class WrennNotFoundError(WrennError):
    """404 — Resource not found."""


class WrennConflictError(WrennError):
    """409 — State conflict (e.g. invalid_state)."""


class WrennHostHasSandboxesError(WrennConflictError):
    """409 — Host still has running sandboxes."""

    def __init__(
        self, code: str, message: str, status_code: int, sandbox_ids: list[str]
    ) -> None:
        self.sandbox_ids = sandbox_ids
        super().__init__(code, message, status_code)


class WrennHostUnavailableError(WrennError):
    """503 — No suitable host available."""


class WrennAgentError(WrennError):
    """502 — Host agent returned an error."""


class WrennInternalError(WrennError):
    """500 — Unexpected server error."""
