"""Git operations inside a Wrenn capsule.

Provides :class:`Git` (sync) and :class:`AsyncGit` (async) interfaces
accessed via ``capsule.git``.  All operations execute the real ``git``
binary inside the capsule through :class:`~wrenn.commands.Commands`.
"""

from __future__ import annotations

import posixpath
import shlex
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import httpx

from wrenn._git._auth import (
    build_credential_approve_cmd,
    embed_credentials,
    is_auth_error,
    strip_credentials,
)
from wrenn._git._cmd import (
    FileStatus,
    GitBranch,
    GitStatus,
    build_add,
    build_branches,
    build_checkout,
    build_clone,
    build_commit,
    build_config_get,
    build_config_set,
    build_create_branch,
    build_delete_branch,
    build_init,
    build_pull,
    build_push,
    build_remote_add,
    build_remote_get_url,
    build_remote_set_url,
    build_reset,
    build_restore,
    build_status,
    parse_branches,
    parse_status,
)
from wrenn._git.exceptions import GitAuthError, GitCommandError, GitError
from wrenn.commands import AsyncCommands, CommandResult, Commands

__all__ = [
    "AsyncGit",
    "FileStatus",
    "Git",
    "GitAuthError",
    "GitBranch",
    "GitCommandError",
    "GitError",
    "GitStatus",
]

_DEFAULT_GIT_ENV: dict[str, str] = {"GIT_TERMINAL_PROMPT": "0"}


def _check_result(result: CommandResult, *, op: str) -> None:
    """Raise a :class:`GitError` subclass if the command failed.

    Args:
        result: Result from ``commands.run()``.
        op: Short operation name for error messages (e.g. ``"clone"``).

    Raises:
        GitAuthError: If stderr contains authentication failure signals.
        GitCommandError: For all other non-zero exit codes.
    """
    if result.exit_code == 0:
        return
    if is_auth_error(result.stderr):
        raise GitAuthError(
            f"git {op}: authentication failed",
            stderr=result.stderr,
            exit_code=result.exit_code,
        )
    msg = result.stderr.strip() or result.stdout.strip()
    raise GitCommandError(
        msg or f"git {op} failed (exit {result.exit_code})",
        stderr=result.stderr,
        exit_code=result.exit_code,
    )


def _merge_envs(envs: dict[str, str] | None) -> dict[str, str]:
    """Merge caller-provided envs with default git environment."""
    return {**_DEFAULT_GIT_ENV, **(envs or {})}


def _derive_repo_dir(url: str) -> str | None:
    """Derive the default repo directory name from a git URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    trimmed = parsed.path.rstrip("/")
    if not trimmed:
        return None
    last = trimmed.split("/")[-1]
    if not last:
        return None
    return last[:-4] if last.endswith(".git") else last


class Git:
    """Sync git interface. Accessed via ``capsule.git``.

    Executes the real ``git`` binary inside the capsule through
    :meth:`Commands.run`. Methods raise :class:`GitCommandError` (or
    :class:`GitAuthError`) on non-zero exit codes.
    """

    def __init__(self, capsule_id: str, http: httpx.Client) -> None:
        self._capsule_id = capsule_id
        self._http = http
        self._commands = Commands(capsule_id, http)

    def _run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Build a shell command from *argv* and execute it."""
        return self._commands.run(
            shlex.join(argv),
            cwd=cwd,
            envs=_merge_envs(envs),
            timeout=timeout,
        )

    def _run_shell(
        self,
        cmd: str,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Execute a raw shell command string."""
        return self._commands.run(
            cmd,
            cwd=cwd,
            envs=_merge_envs(envs),
            timeout=timeout,
        )

    # ── Repository setup ───────────────────────────────────────

    def clone(
        self,
        url: str,
        dest: str | None = None,
        *,
        branch: str | None = None,
        depth: int | None = None,
        username: str | None = None,
        password: str | None = None,
        dangerously_store_credentials: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 300,
    ) -> CommandResult:
        """Clone a remote repository into the capsule.

        Args:
            url: Remote repository URL.
            dest: Destination path. Defaults to the repository name
                derived from the URL.
            branch: Branch or tag to check out.
            depth: Create a shallow clone with this many commits.
            username: Username for HTTP(S) authentication.
            password: Password or token for HTTP(S) authentication.
            dangerously_store_credentials: If ``True``, leave credentials
                embedded in the remote URL after cloning.
            cwd: Working directory for the command.
            envs: Extra environment variables.
            timeout: Command timeout in seconds. Defaults to ``300``.

        Returns:
            Command result with stdout, stderr, exit_code, and duration.

        Raises:
            GitAuthError: If the remote rejected authentication.
            GitCommandError: If clone failed for another reason.
            ValueError: If *password* is provided without *username*.
        """
        if password and not username:
            raise ValueError(
                "Username is required when using a password for git clone."
            )

        clone_url = url
        if username and password:
            clone_url = embed_credentials(url, username, password)

        argv = build_clone(clone_url, dest, branch=branch, depth=depth)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="clone")

        if username and password and not dangerously_store_credentials:
            sanitized = strip_credentials(clone_url)
            if sanitized != clone_url:
                repo_dir = dest or _derive_repo_dir(url)
                if repo_dir:
                    repo_cwd = posixpath.join(cwd, repo_dir) if cwd else repo_dir
                    strip_result = self._run(
                        build_remote_set_url("origin", sanitized),
                        cwd=repo_cwd,
                        envs=envs,
                    )
                    _check_result(strip_result, op="clone (strip credentials)")

        return result

    def init(
        self,
        path: str = ".",
        *,
        bare: bool = False,
        initial_branch: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Initialize a new git repository.

        Args:
            path: Destination path for the repository.
            bare: Create a bare repository.
            initial_branch: Name for the initial branch (e.g. ``"main"``).
            cwd: Working directory for the command.
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If init failed.
        """
        argv = build_init(path, bare=bare, initial_branch=initial_branch)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="init")
        return result

    # ── Staging and committing ─────────────────────────────────

    def add(
        self,
        paths: list[str] | None = None,
        *,
        all: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Stage files for commit.

        Args:
            paths: Specific files to stage. If ``None``, stages the
                current directory (or all with ``all=True``).
            all: Stage all changes including untracked files.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If add failed.
        """
        argv = build_add(paths, all=all)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="add")
        return result

    def commit(
        self,
        message: str,
        *,
        allow_empty: bool = False,
        author_name: str | None = None,
        author_email: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Create a commit.

        Args:
            message: Commit message.
            allow_empty: Allow creating a commit with no changes.
            author_name: Override the commit author name.
            author_email: Override the commit author email.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If commit failed.
        """
        argv = build_commit(
            message,
            allow_empty=allow_empty,
            author_name=author_name,
            author_email=author_email,
        )
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="commit")
        return result

    # ── Remote sync ────────────────────────────────────────────

    def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        *,
        force: bool = False,
        set_upstream: bool = False,
        username: str | None = None,
        password: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 60,
    ) -> CommandResult:
        """Push commits to a remote.

        Args:
            remote: Remote name. Defaults to ``"origin"``.
            branch: Branch to push. Defaults to the current branch.
            force: Force-push.
            set_upstream: Set upstream tracking reference.
            username: Username for HTTP(S) authentication.
            password: Password or token for HTTP(S) authentication.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitAuthError: If authentication failed.
            GitCommandError: If push failed.
        """
        if username and password:
            return self._with_remote_credentials(
                remote=remote,
                username=username,
                password=password,
                operation=lambda: self._run(
                    build_push(remote, branch, force=force, set_upstream=set_upstream),
                    cwd=cwd,
                    envs=envs,
                    timeout=timeout,
                ),
                cwd=cwd,
                envs=envs,
                timeout=timeout,
                op="push",
            )

        argv = build_push(remote, branch, force=force, set_upstream=set_upstream)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="push")
        return result

    def pull(
        self,
        remote: str = "origin",
        branch: str | None = None,
        *,
        rebase: bool = False,
        ff_only: bool = False,
        username: str | None = None,
        password: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 60,
    ) -> CommandResult:
        """Pull changes from a remote.

        Args:
            remote: Remote name. Defaults to ``"origin"``.
            branch: Branch to pull.
            rebase: Rebase instead of merge.
            ff_only: Only allow fast-forward merges.
            username: Username for HTTP(S) authentication.
            password: Password or token for HTTP(S) authentication.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitAuthError: If authentication failed.
            GitCommandError: If pull failed.
        """
        if username and password:
            return self._with_remote_credentials(
                remote=remote,
                username=username,
                password=password,
                operation=lambda: self._run(
                    build_pull(remote, branch, rebase=rebase, ff_only=ff_only),
                    cwd=cwd,
                    envs=envs,
                    timeout=timeout,
                ),
                cwd=cwd,
                envs=envs,
                timeout=timeout,
                op="pull",
            )

        argv = build_pull(remote, branch, rebase=rebase, ff_only=ff_only)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="pull")
        return result

    # ── Status and branches ────────────────────────────────────

    def status(
        self,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> GitStatus:
        """Get repository status.

        Args:
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Parsed :class:`GitStatus` with branch info and file changes.

        Raises:
            GitCommandError: If the command failed.
        """
        result = self._run(build_status(), cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="status")
        return parse_status(result.stdout)

    def branches(
        self,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> list[GitBranch]:
        """List local branches.

        Args:
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            List of :class:`GitBranch`.

        Raises:
            GitCommandError: If the command failed.
        """
        result = self._run(build_branches(), cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="branches")
        return parse_branches(result.stdout)

    def create_branch(
        self,
        name: str,
        *,
        start_point: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Create and check out a new branch.

        Args:
            name: Branch name.
            start_point: Commit or ref to branch from.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_create_branch(name, start_point=start_point)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="create_branch")
        return result

    def checkout_branch(
        self,
        name: str,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Check out an existing branch.

        Args:
            name: Branch name.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_checkout(name)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="checkout_branch")
        return result

    def delete_branch(
        self,
        name: str,
        *,
        force: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Delete a branch.

        Args:
            name: Branch name.
            force: Force-delete with ``-D``.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_delete_branch(name, force=force)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="delete_branch")
        return result

    # ── Remotes ────────────────────────────────────────────────

    def remote_add(
        self,
        name: str,
        url: str,
        *,
        fetch: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Add a remote.

        Args:
            name: Remote name (e.g. ``"origin"``).
            url: Remote URL.
            fetch: Fetch after adding.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_remote_add(name, url, fetch=fetch)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="remote_add")
        return result

    def remote_get(
        self,
        name: str = "origin",
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> str | None:
        """Get the URL of a remote.

        Returns ``None`` if the remote does not exist rather than raising.

        Args:
            name: Remote name. Defaults to ``"origin"``.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Remote URL or ``None``.
        """
        result = self._run(
            build_remote_get_url(name), cwd=cwd, envs=envs, timeout=timeout
        )
        if result.exit_code != 0:
            return None
        url = result.stdout.strip()
        return url or None

    # ── Reset and restore ──────────────────────────────────────

    def reset(
        self,
        *,
        mode: str | None = None,
        ref: str | None = None,
        paths: list[str] | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Reset the current HEAD.

        Args:
            mode: Reset mode (``soft``, ``mixed``, ``hard``, ``merge``,
                ``keep``).
            ref: Commit, branch, or ref to reset to.
            paths: Paths to reset.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_reset(mode=mode, ref=ref, paths=paths)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="reset")
        return result

    def restore(
        self,
        paths: list[str],
        *,
        staged: bool = False,
        worktree: bool = False,
        source: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Restore working-tree files or unstage changes.

        Args:
            paths: Paths to restore.
            staged: Restore the index (unstage).
            worktree: Restore working-tree files.
            source: Commit or ref to restore from.
            cwd: Working directory (repository root).
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_restore(paths, staged=staged, worktree=worktree, source=source)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="restore")
        return result

    # ── Configuration ──────────────────────────────────────────

    def set_config(
        self,
        key: str,
        value: str,
        *,
        scope: str = "local",
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Set a git config value.

        Args:
            key: Config key (e.g. ``"user.name"``).
            value: Config value.
            scope: Config scope: ``"local"``, ``"global"``, or
                ``"system"``.
            cwd: Working directory (repository root). Required when
                scope is ``"local"``.
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Command result.

        Raises:
            GitCommandError: If the command failed.
        """
        argv = build_config_set(key, value, scope=scope, repo_path=cwd)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="set_config")
        return result

    def get_config(
        self,
        key: str,
        *,
        scope: str = "local",
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> str | None:
        """Get a git config value.

        Returns ``None`` if the key is not set rather than raising.

        Args:
            key: Config key (e.g. ``"user.name"``).
            scope: Config scope: ``"local"``, ``"global"``, or
                ``"system"``.
            cwd: Working directory (repository root). Required when
                scope is ``"local"``.
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Returns:
            Config value or ``None``.
        """
        argv = build_config_get(key, scope=scope, repo_path=cwd)
        result = self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        if result.exit_code != 0:
            return None
        val = result.stdout.strip()
        return val or None

    def configure_user(
        self,
        name: str,
        email: str,
        *,
        scope: str = "global",
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> None:
        """Configure git user name and email.

        Args:
            name: Git user name.
            email: Git user email.
            scope: Config scope. Defaults to ``"global"``.
            cwd: Working directory (repository root). Required when
                scope is ``"local"``.
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Raises:
            ValueError: If *name* or *email* is empty.
            GitCommandError: If a config command failed.
        """
        if not name or not email:
            raise ValueError("Both name and email are required.")
        self.set_config(
            "user.name", name, scope=scope, cwd=cwd, envs=envs, timeout=timeout
        )
        self.set_config(
            "user.email", email, scope=scope, cwd=cwd, envs=envs, timeout=timeout
        )

    def dangerously_authenticate(
        self,
        username: str,
        password: str,
        host: str = "github.com",
        protocol: str = "https",
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> None:
        """Persist git credentials via the credential store.

        .. warning::

            Credentials are written in plain text to the capsule
            filesystem and are accessible to any process running inside
            the capsule.  Prefer per-operation ``username``/``password``
            parameters on :meth:`clone`, :meth:`push`, and :meth:`pull`
            instead.

        Args:
            username: Git username.
            password: Password or personal access token.
            host: Target host. Defaults to ``"github.com"``.
            protocol: Protocol. Defaults to ``"https"``.
            cwd: Working directory.
            envs: Extra environment variables.
            timeout: Command timeout in seconds.

        Raises:
            ValueError: If *username* or *password* is empty.
            GitCommandError: If a command failed.
        """
        if not username or not password:
            raise ValueError("Both username and password are required.")
        self.set_config(
            "credential.helper",
            "store",
            scope="global",
            cwd=cwd,
            envs=envs,
            timeout=timeout,
        )
        cmd = build_credential_approve_cmd(
            username=username,
            password=password,
            host=host,
            protocol=protocol,
        )
        result = self._run_shell(cmd, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="dangerously_authenticate")

    # ── Credential helper for push/pull ────────────────────────

    def _with_remote_credentials(
        self,
        *,
        remote: str,
        username: str,
        password: str,
        operation: Callable[[], CommandResult],
        cwd: str | None,
        envs: dict[str, str] | None,
        timeout: int | None,
        op: str,
    ) -> CommandResult:
        """Temporarily embed credentials in a remote URL, run an operation,
        then restore the original URL.
        """
        original_url = self.remote_get(remote, cwd=cwd, envs=envs, timeout=timeout)
        if not original_url:
            raise GitCommandError(
                f"Remote '{remote}' not found.",
                stderr="",
                exit_code=1,
            )

        credential_url = embed_credentials(original_url, username, password)
        self._run(
            build_remote_set_url(remote, credential_url),
            cwd=cwd,
            envs=envs,
            timeout=timeout,
        )

        op_error: Exception | None = None
        result: CommandResult | None = None
        try:
            result = operation()
            _check_result(result, op=op)
        except Exception as err:
            op_error = err

        restore_error: Exception | None = None
        try:
            self._run(
                build_remote_set_url(remote, original_url),
                cwd=cwd,
                envs=envs,
                timeout=timeout,
            )
        except Exception as err:
            restore_error = err

        if op_error:
            raise op_error
        if restore_error:
            raise restore_error

        assert result is not None
        return result


class AsyncGit:
    """Async git interface. Accessed via ``capsule.git``.

    Async mirror of :class:`Git`. See that class for full method
    documentation.
    """

    def __init__(self, capsule_id: str, http: httpx.AsyncClient) -> None:
        self._capsule_id = capsule_id
        self._http = http
        self._commands = AsyncCommands(capsule_id, http)

    async def _run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Build a shell command from *argv* and execute it."""
        return await self._commands.run(
            shlex.join(argv),
            cwd=cwd,
            envs=_merge_envs(envs),
            timeout=timeout,
        )

    async def _run_shell(
        self,
        cmd: str,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Execute a raw shell command string."""
        return await self._commands.run(
            cmd,
            cwd=cwd,
            envs=_merge_envs(envs),
            timeout=timeout,
        )

    # ── Repository setup ───────────────────────────────────────

    async def clone(
        self,
        url: str,
        dest: str | None = None,
        *,
        branch: str | None = None,
        depth: int | None = None,
        username: str | None = None,
        password: str | None = None,
        dangerously_store_credentials: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 300,
    ) -> CommandResult:
        """Clone a remote repository into the capsule."""
        if password and not username:
            raise ValueError(
                "Username is required when using a password for git clone."
            )

        clone_url = url
        if username and password:
            clone_url = embed_credentials(url, username, password)

        argv = build_clone(clone_url, dest, branch=branch, depth=depth)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="clone")

        if username and password and not dangerously_store_credentials:
            sanitized = strip_credentials(clone_url)
            if sanitized != clone_url:
                repo_dir = dest or _derive_repo_dir(url)
                if repo_dir:
                    repo_cwd = posixpath.join(cwd, repo_dir) if cwd else repo_dir
                    strip_result = await self._run(
                        build_remote_set_url("origin", sanitized),
                        cwd=repo_cwd,
                        envs=envs,
                    )
                    _check_result(strip_result, op="clone (strip credentials)")

        return result

    async def init(
        self,
        path: str = ".",
        *,
        bare: bool = False,
        initial_branch: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Initialize a new git repository."""
        argv = build_init(path, bare=bare, initial_branch=initial_branch)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="init")
        return result

    # ── Staging and committing ─────────────────────────────────

    async def add(
        self,
        paths: list[str] | None = None,
        *,
        all: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Stage files for commit."""
        argv = build_add(paths, all=all)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="add")
        return result

    async def commit(
        self,
        message: str,
        *,
        allow_empty: bool = False,
        author_name: str | None = None,
        author_email: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Create a commit."""
        argv = build_commit(
            message,
            allow_empty=allow_empty,
            author_name=author_name,
            author_email=author_email,
        )
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="commit")
        return result

    # ── Remote sync ────────────────────────────────────────────

    async def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        *,
        force: bool = False,
        set_upstream: bool = False,
        username: str | None = None,
        password: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 60,
    ) -> CommandResult:
        """Push commits to a remote."""
        if username and password:

            async def _op() -> CommandResult:
                return await self._run(
                    build_push(remote, branch, force=force, set_upstream=set_upstream),
                    cwd=cwd,
                    envs=envs,
                    timeout=timeout,
                )

            return await self._with_remote_credentials(
                remote=remote,
                username=username,
                password=password,
                operation=_op,
                cwd=cwd,
                envs=envs,
                timeout=timeout,
                op="push",
            )

        argv = build_push(remote, branch, force=force, set_upstream=set_upstream)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="push")
        return result

    async def pull(
        self,
        remote: str = "origin",
        branch: str | None = None,
        *,
        rebase: bool = False,
        ff_only: bool = False,
        username: str | None = None,
        password: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 60,
    ) -> CommandResult:
        """Pull changes from a remote."""
        if username and password:

            async def _op() -> CommandResult:
                return await self._run(
                    build_pull(remote, branch, rebase=rebase, ff_only=ff_only),
                    cwd=cwd,
                    envs=envs,
                    timeout=timeout,
                )

            return await self._with_remote_credentials(
                remote=remote,
                username=username,
                password=password,
                operation=_op,
                cwd=cwd,
                envs=envs,
                timeout=timeout,
                op="pull",
            )

        argv = build_pull(remote, branch, rebase=rebase, ff_only=ff_only)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="pull")
        return result

    # ── Status and branches ────────────────────────────────────

    async def status(
        self,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> GitStatus:
        """Get repository status."""
        result = await self._run(build_status(), cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="status")
        return parse_status(result.stdout)

    async def branches(
        self,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> list[GitBranch]:
        """List local branches."""
        result = await self._run(build_branches(), cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="branches")
        return parse_branches(result.stdout)

    async def create_branch(
        self,
        name: str,
        *,
        start_point: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Create and check out a new branch."""
        argv = build_create_branch(name, start_point=start_point)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="create_branch")
        return result

    async def checkout_branch(
        self,
        name: str,
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Check out an existing branch."""
        argv = build_checkout(name)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="checkout_branch")
        return result

    async def delete_branch(
        self,
        name: str,
        *,
        force: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Delete a branch."""
        argv = build_delete_branch(name, force=force)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="delete_branch")
        return result

    # ── Remotes ────────────────────────────────────────────────

    async def remote_add(
        self,
        name: str,
        url: str,
        *,
        fetch: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Add a remote."""
        argv = build_remote_add(name, url, fetch=fetch)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="remote_add")
        return result

    async def remote_get(
        self,
        name: str = "origin",
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> str | None:
        """Get the URL of a remote. Returns ``None`` if not found."""
        result = await self._run(
            build_remote_get_url(name), cwd=cwd, envs=envs, timeout=timeout
        )
        if result.exit_code != 0:
            return None
        url = result.stdout.strip()
        return url or None

    # ── Reset and restore ──────────────────────────────────────

    async def reset(
        self,
        *,
        mode: str | None = None,
        ref: str | None = None,
        paths: list[str] | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Reset the current HEAD."""
        argv = build_reset(mode=mode, ref=ref, paths=paths)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="reset")
        return result

    async def restore(
        self,
        paths: list[str],
        *,
        staged: bool = False,
        worktree: bool = False,
        source: str | None = None,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Restore working-tree files or unstage changes."""
        argv = build_restore(paths, staged=staged, worktree=worktree, source=source)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="restore")
        return result

    # ── Configuration ──────────────────────────────────────────

    async def set_config(
        self,
        key: str,
        value: str,
        *,
        scope: str = "local",
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> CommandResult:
        """Set a git config value."""
        argv = build_config_set(key, value, scope=scope, repo_path=cwd)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="set_config")
        return result

    async def get_config(
        self,
        key: str,
        *,
        scope: str = "local",
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> str | None:
        """Get a git config value. Returns ``None`` if not set."""
        argv = build_config_get(key, scope=scope, repo_path=cwd)
        result = await self._run(argv, cwd=cwd, envs=envs, timeout=timeout)
        if result.exit_code != 0:
            return None
        val = result.stdout.strip()
        return val or None

    async def configure_user(
        self,
        name: str,
        email: str,
        *,
        scope: str = "global",
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> None:
        """Configure git user name and email."""
        if not name or not email:
            raise ValueError("Both name and email are required.")
        await self.set_config(
            "user.name", name, scope=scope, cwd=cwd, envs=envs, timeout=timeout
        )
        await self.set_config(
            "user.email", email, scope=scope, cwd=cwd, envs=envs, timeout=timeout
        )

    async def dangerously_authenticate(
        self,
        username: str,
        password: str,
        host: str = "github.com",
        protocol: str = "https",
        *,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30,
    ) -> None:
        """Persist git credentials via the credential store.

        .. warning::

            Credentials are written in plain text to the capsule
            filesystem.  Prefer per-operation ``username``/``password``
            parameters instead.
        """
        if not username or not password:
            raise ValueError("Both username and password are required.")
        await self.set_config(
            "credential.helper",
            "store",
            scope="global",
            cwd=cwd,
            envs=envs,
            timeout=timeout,
        )
        cmd = build_credential_approve_cmd(
            username=username,
            password=password,
            host=host,
            protocol=protocol,
        )
        result = await self._run_shell(cmd, cwd=cwd, envs=envs, timeout=timeout)
        _check_result(result, op="dangerously_authenticate")

    # ── Credential helper for push/pull ────────────────────────

    async def _with_remote_credentials(
        self,
        *,
        remote: str,
        username: str,
        password: str,
        operation: Callable[[], Awaitable[CommandResult]],
        cwd: str | None,
        envs: dict[str, str] | None,
        timeout: int | None,
        op: str,
    ) -> CommandResult:
        """Temporarily embed credentials in a remote URL, run an operation,
        then restore the original URL.
        """
        original_url = await self.remote_get(
            remote, cwd=cwd, envs=envs, timeout=timeout
        )
        if not original_url:
            raise GitCommandError(
                f"Remote '{remote}' not found.",
                stderr="",
                exit_code=1,
            )

        credential_url = embed_credentials(original_url, username, password)
        await self._run(
            build_remote_set_url(remote, credential_url),
            cwd=cwd,
            envs=envs,
            timeout=timeout,
        )

        op_error: Exception | None = None
        result: CommandResult | None = None
        try:
            result = await operation()
            _check_result(result, op=op)
        except Exception as err:
            op_error = err

        restore_error: Exception | None = None
        try:
            await self._run(
                build_remote_set_url(remote, original_url),
                cwd=cwd,
                envs=envs,
                timeout=timeout,
            )
        except Exception as err:
            restore_error = err

        if op_error:
            raise op_error
        if restore_error:
            raise restore_error

        assert result is not None
        return result
