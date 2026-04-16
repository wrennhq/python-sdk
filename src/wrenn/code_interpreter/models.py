from __future__ import annotations

from dataclasses import dataclass, field

_MIME_MAP: dict[str, str] = {
    "text/plain": "text",
    "text/html": "html",
    "text/markdown": "markdown",
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "application/pdf": "pdf",
    "text/latex": "latex",
    "application/json": "json",
    "application/javascript": "javascript",
}


@dataclass
class ExecutionError:
    """Error raised during code execution.

    Attributes:
        name: Exception class name (e.g. ``"NameError"``).
        value: Exception message.
        traceback: Full traceback string.
    """

    name: str = ""
    value: str = ""
    traceback: str = ""


@dataclass
class Logs:
    """Captured stdout/stderr streams.

    Each element in the list is one chunk of text as it arrived from
    the kernel.
    """

    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)


@dataclass
class Result:
    """A single rich output from code execution.

    Jupyter cells can produce multiple outputs — one ``execute_result``
    (the expression value) and zero or more ``display_data`` messages
    (from ``plt.show()``, ``display()``, etc.).  Each becomes a
    ``Result``.

    Known MIME types are unpacked into named attributes; anything else
    lands in :pyattr:`extra`.
    """

    # --- MIME type fields ---
    text: str | None = None
    """``text/plain`` representation."""
    html: str | None = None
    """``text/html`` representation."""
    markdown: str | None = None
    """``text/markdown`` representation."""
    svg: str | None = None
    """``image/svg+xml`` representation."""
    png: str | None = None
    """``image/png`` — base64-encoded."""
    jpeg: str | None = None
    """``image/jpeg`` — base64-encoded."""
    pdf: str | None = None
    """``application/pdf`` — base64-encoded."""
    latex: str | None = None
    """``text/latex`` representation."""
    json: dict | None = None
    """``application/json`` representation."""
    javascript: str | None = None
    """``application/javascript`` representation."""
    extra: dict[str, str] | None = None
    """MIME types not covered by the named fields above."""

    is_main_result: bool = False
    """``True`` when this came from an ``execute_result`` message
    (i.e. the value of the last expression in the cell).  ``False``
    for ``display_data`` outputs."""

    @classmethod
    def from_bundle(
        cls, bundle: dict[str, str], *, is_main_result: bool = False
    ) -> Result:
        """Build a ``Result`` from a Jupyter MIME bundle dict."""
        kwargs: dict = {"is_main_result": is_main_result}
        extra: dict[str, str] = {}
        for mime, value in bundle.items():
            attr = _MIME_MAP.get(mime)
            if attr is not None:
                kwargs[attr] = value
            else:
                extra[mime] = value
        if extra:
            kwargs["extra"] = extra
        # Strip surrounding quotes from text/plain (Jupyter repr artefact)
        text = kwargs.get("text")
        if isinstance(text, str) and len(text) >= 2:
            if (text[0] == text[-1]) and text[0] in ("'", '"'):
                kwargs["text"] = text[1:-1]
        return cls(**kwargs)

    def formats(self) -> list[str]:
        """Return names of non-``None`` MIME-type fields."""
        out: list[str] = []
        for attr in (
            "text",
            "html",
            "markdown",
            "svg",
            "png",
            "jpeg",
            "pdf",
            "latex",
            "json",
            "javascript",
        ):
            if getattr(self, attr) is not None:
                out.append(attr)
        if self.extra:
            out.extend(self.extra)
        return out


@dataclass
class Execution:
    """Complete result of a ``run_code`` call.

    Attributes:
        results: All rich outputs produced by the cell — charts, tables,
            images, expression values, etc.
        logs: Captured stdout/stderr text.
        error: Populated when the cell raised an exception.
        execution_count: Jupyter execution counter (the ``[N]`` number).
    """

    results: list[Result] = field(default_factory=list)
    logs: Logs = field(default_factory=Logs)
    error: ExecutionError | None = None
    execution_count: int | None = None

    @property
    def text(self) -> str | None:
        """Convenience — ``text/plain`` of the main ``execute_result``,
        or ``None`` if the cell had no expression value."""
        for r in self.results:
            if r.is_main_result:
                return r.text
        return None
