from __future__ import annotations

import shlex
from urllib.parse import urlparse, urlunparse


def embed_credentials(url: str, username: str, password: str) -> str:
    """Embed HTTP(S) credentials into a git URL.

    Args:
        url: Git repository URL.
        username: Username for authentication.
        password: Password or personal access token.

    Returns:
        URL with ``username:password@`` embedded in the netloc.

    Raises:
        ValueError: If the URL scheme is not ``http`` or ``https``.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            "Only http(s) URLs support embedded credentials."
        )
    netloc = f"{username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def strip_credentials(url: str) -> str:
    """Remove embedded credentials from a git URL.

    Args:
        url: Git repository URL, possibly with credentials.

    Returns:
        URL with credentials removed. Non-HTTP(S) URLs are returned
        unchanged.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url
    if not parsed.username and not parsed.password:
        return url
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=host))


def is_auth_error(stderr: str) -> bool:
    """Check whether git stderr indicates an authentication failure.

    Args:
        stderr: Combined stderr output from a git command.

    Returns:
        ``True`` if any known auth-failure pattern is found.
    """
    lower = stderr.lower()
    patterns = (
        "authentication failed",
        "terminal prompts disabled",
        "could not read username",
        "invalid username or password",
        "access denied",
        "permission denied",
        "not authorized",
    )
    return any(p in lower for p in patterns)


def build_credential_approve_cmd(
    username: str,
    password: str,
    host: str = "github.com",
    protocol: str = "https",
) -> str:
    """Build a shell command that pipes credentials into ``git credential approve``.

    Args:
        username: Git username.
        password: Password or personal access token.
        host: Target host. Defaults to ``"github.com"``.
        protocol: Protocol. Defaults to ``"https"``.

    Returns:
        A shell command string safe to pass to ``commands.run()``.
    """
    if "\n" in username or "\n" in password:
        raise ValueError("Credentials must not contain newline characters.")
    target_host = host.strip() or "github.com"
    target_protocol = protocol.strip() or "https"
    credential_input = "\n".join([
        f"protocol={target_protocol}",
        f"host={target_host}",
        f"username={username}",
        f"password={password}",
        "",
        "",
    ])
    return f"printf %s {shlex.quote(credential_input)} | git credential approve"
