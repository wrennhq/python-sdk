from __future__ import annotations

import httpx


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


_ERROR_MAP: dict[str, type[WrennError]] = {
    "invalid_request": WrennValidationError,
    "unauthorized": WrennAuthenticationError,
    "forbidden": WrennForbiddenError,
    "not_found": WrennNotFoundError,
    "invalid_state": WrennConflictError,
    "conflict": WrennConflictError,
    "host_has_sandboxes": WrennHostHasSandboxesError,
    "host_unavailable": WrennHostUnavailableError,
    "agent_error": WrennAgentError,
    "internal_error": WrennInternalError,
}


def handle_response(resp: httpx.Response) -> dict | list:
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            resp.raise_for_status()
            raise

        err = body.get("error", {})
        code = err.get("code", "internal_error")
        message = err.get("message", resp.text)

        exc_cls = _ERROR_MAP.get(code, WrennError)

        if exc_cls is WrennHostHasSandboxesError:
            raise WrennHostHasSandboxesError(
                code=code,
                message=message,
                status_code=resp.status_code,
                sandbox_ids=body.get("sandbox_ids", []),
            )

        raise exc_cls(
            code=code,
            message=message,
            status_code=resp.status_code,
        )

    if resp.status_code == 204:
        return {}

    return resp.json()
