from __future__ import annotations

import warnings

import httpx


class WrennError(Exception):
    """Base exception for all Wrenn SDK errors.

    All SDK exceptions inherit from this class, so you can catch
    ``WrennError`` to handle any API error generically.

    Attributes:
        code (str): Machine-readable error code from the API
            (e.g. ``"not_found"``).
        message (str): Human-readable error description.
        status_code (int): HTTP status code of the response.
    """

    def __init__(self, code: str, message: str, status_code: int) -> None:
        """Initialize a WrennError.

        Args:
            code (str): Machine-readable error code.
            message (str): Human-readable error description.
            status_code (int): HTTP status code of the response.
        """
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


class WrennHostHasCapsulesError(WrennConflictError):
    """409 — Host still has running capsules.

    Attributes:
        capsule_ids (list[str]): IDs of the capsules still running on the host.
    """

    def __init__(
        self, code: str, message: str, status_code: int, capsule_ids: list[str]
    ) -> None:
        """Initialize a WrennHostHasCapsulesError.

        Args:
            code (str): Machine-readable error code.
            message (str): Human-readable error description.
            status_code (int): HTTP status code of the response.
            capsule_ids (list[str]): IDs of capsules still on the host.
        """
        self.capsule_ids = capsule_ids
        super().__init__(code, message, status_code)

    @property
    def sandbox_ids(self) -> list[str]:
        warnings.warn(
            "'sandbox_ids' is deprecated, use 'capsule_ids' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.capsule_ids


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
    "host_has_sandboxes": WrennHostHasCapsulesError,
    "host_has_capsules": WrennHostHasCapsulesError,
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

        if exc_cls is WrennHostHasCapsulesError:
            raise WrennHostHasCapsulesError(
                code=code,
                message=message,
                status_code=resp.status_code,
                capsule_ids=body.get("sandbox_ids", []),
            )

        raise exc_cls(
            code=code,
            message=message,
            status_code=resp.status_code,
        )

    if resp.status_code == 204:
        return {}

    return resp.json()


def __getattr__(name: str) -> type:
    if name == "WrennHostHasSandboxesError":
        warnings.warn(
            "'WrennHostHasSandboxesError' is deprecated, use 'WrennHostHasCapsulesError' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return WrennHostHasCapsulesError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
