from __future__ import annotations


class GitError(Exception):
    """Base exception for all git operations inside a capsule.

    Not a subclass of :class:`WrennError` because git errors originate
    from a process exit code, not an HTTP response.

    Attributes:
        message (str): Human-readable error description.
        stderr (str): Raw stderr output from the git process.
        exit_code (int): Process exit code.
    """

    def __init__(self, message: str, *, stderr: str = "", exit_code: int = -1) -> None:
        self.message = message
        self.stderr = stderr
        self.exit_code = exit_code
        super().__init__(message)


class GitCommandError(GitError):
    """A git command exited with a non-zero exit code."""


class GitAuthError(GitError):
    """Authentication failed when communicating with a remote."""
