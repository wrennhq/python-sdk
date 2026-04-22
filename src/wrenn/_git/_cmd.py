"""Pure functions that build git argument lists and parse git output.

No I/O, no network, no imports from ``wrenn``. Every ``build_*`` function
returns a ``list[str]`` suitable for ``shlex.join()``.  Every ``parse_*``
function takes raw stdout and returns a typed structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Data types ─────────────────────────────────────────────────────

@dataclass
class FileStatus:
    """A single entry from ``git status --porcelain=v1``.

    Attributes:
        path (str): File path relative to the repository root.
        index_status (str): Index (staged) status character.
        work_tree_status (str): Working-tree status character.
        renamed_from (str | None): Original path when status is a rename.
    """

    path: str
    index_status: str
    work_tree_status: str
    renamed_from: str | None = None

    @property
    def staged(self) -> bool:
        """Whether the change is staged in the index."""
        return self.index_status not in (" ", "?")

    @property
    def status(self) -> str:
        """Normalized human-readable status label."""
        return _derive_status(self.index_status, self.work_tree_status)


@dataclass
class GitStatus:
    """Parsed output of ``git status --porcelain=v1 --branch``.

    Attributes:
        branch (str | None): Current branch name, or ``None`` if detached.
        upstream (str | None): Upstream tracking branch.
        ahead (int): Commits ahead of upstream.
        behind (int): Commits behind upstream.
        detached (bool): Whether HEAD is detached.
        files (list[FileStatus]): Per-file status entries.
    """

    branch: str | None = None
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    detached: bool = False
    files: list[FileStatus] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """``True`` when there are no changed or untracked files."""
        return len(self.files) == 0

    @property
    def has_staged(self) -> bool:
        """``True`` when at least one file has staged changes."""
        return any(f.staged for f in self.files)

    @property
    def has_untracked(self) -> bool:
        """``True`` when at least one file is untracked."""
        return any(f.status == "untracked" for f in self.files)

    @property
    def has_conflicts(self) -> bool:
        """``True`` when at least one file has merge conflicts."""
        return any(f.status == "conflict" for f in self.files)


@dataclass
class GitBranch:
    """A single branch entry.

    Attributes:
        name (str): Branch name (short ref).
        is_current (bool): Whether this is the checked-out branch.
    """

    name: str
    is_current: bool = False


# ── Argument builders ──────────────────────────────────────────────

def build_clone(
    url: str,
    dest: str | None = None,
    *,
    branch: str | None = None,
    depth: int | None = None,
) -> list[str]:
    """Build ``git clone`` arguments."""
    args = ["git", "clone"]
    if branch:
        args.extend(["--branch", branch, "--single-branch"])
    if depth is not None:
        args.extend(["--depth", str(depth)])
    args.append(url)
    if dest:
        args.append(dest)
    return args


def build_init(
    path: str = ".",
    *,
    bare: bool = False,
    initial_branch: str | None = None,
) -> list[str]:
    """Build ``git init`` arguments."""
    args = ["git", "init"]
    if initial_branch:
        args.extend(["--initial-branch", initial_branch])
    if bare:
        args.append("--bare")
    args.append(path)
    return args


def build_add(
    paths: list[str] | None = None,
    *,
    all: bool = False,
) -> list[str]:
    """Build ``git add`` arguments."""
    args = ["git", "add"]
    if not paths:
        args.append("-A" if all else ".")
    else:
        args.append("--")
        args.extend(paths)
    return args


def build_commit(
    message: str,
    *,
    allow_empty: bool = False,
    author_name: str | None = None,
    author_email: str | None = None,
) -> list[str]:
    """Build ``git commit`` arguments."""
    args = ["git"]
    if author_name:
        args.extend(["-c", f"user.name={author_name}"])
    if author_email:
        args.extend(["-c", f"user.email={author_email}"])
    args.extend(["commit", "-m", message])
    if allow_empty:
        args.append("--allow-empty")
    return args


def build_push(
    remote: str = "origin",
    branch: str | None = None,
    *,
    force: bool = False,
    set_upstream: bool = False,
) -> list[str]:
    """Build ``git push`` arguments."""
    args = ["git", "push"]
    if force:
        args.append("--force")
    if set_upstream:
        args.append("--set-upstream")
    args.append(remote)
    if branch:
        args.append(branch)
    return args


def build_pull(
    remote: str = "origin",
    branch: str | None = None,
    *,
    rebase: bool = False,
    ff_only: bool = False,
) -> list[str]:
    """Build ``git pull`` arguments."""
    args = ["git", "pull"]
    if rebase:
        args.append("--rebase")
    if ff_only:
        args.append("--ff-only")
    args.append(remote)
    if branch:
        args.append(branch)
    return args


def build_status() -> list[str]:
    """Build ``git status`` arguments for porcelain parsing."""
    return ["git", "status", "--porcelain=v1", "--branch"]


def build_branches() -> list[str]:
    """Build ``git branch`` arguments for structured parsing."""
    return ["git", "branch", "--format=%(refname:short)\t%(HEAD)"]


def build_create_branch(
    name: str,
    *,
    start_point: str | None = None,
) -> list[str]:
    """Build ``git checkout -b`` arguments."""
    args = ["git", "checkout", "-b", name]
    if start_point:
        args.append(start_point)
    return args


def build_checkout(name: str) -> list[str]:
    """Build ``git checkout`` arguments."""
    return ["git", "checkout", name]


def build_delete_branch(
    name: str,
    *,
    force: bool = False,
) -> list[str]:
    """Build ``git branch -d/-D`` arguments."""
    return ["git", "branch", "-D" if force else "-d", name]


def build_remote_add(name: str, url: str, *, fetch: bool = False) -> list[str]:
    """Build ``git remote add`` arguments."""
    args = ["git", "remote", "add"]
    if fetch:
        args.append("-f")
    args.extend([name, url])
    return args


def build_remote_get_url(name: str = "origin") -> list[str]:
    """Build ``git remote get-url`` arguments."""
    return ["git", "remote", "get-url", name]


def build_remote_set_url(name: str, url: str) -> list[str]:
    """Build ``git remote set-url`` arguments."""
    return ["git", "remote", "set-url", name, url]


def build_reset(
    *,
    mode: str | None = None,
    ref: str | None = None,
    paths: list[str] | None = None,
) -> list[str]:
    """Build ``git reset`` arguments.

    Args:
        mode: Reset mode (``soft``, ``mixed``, ``hard``, ``merge``, ``keep``).
        ref: Commit, branch, or ref to reset to.
        paths: Paths to reset (mutually exclusive with ``mode``).
    """
    _ALLOWED_MODES = {"soft", "mixed", "hard", "merge", "keep"}
    if mode and mode not in _ALLOWED_MODES:
        raise ValueError(
            f"Reset mode must be one of {', '.join(sorted(_ALLOWED_MODES))}."
        )
    args = ["git", "reset"]
    if mode:
        args.append(f"--{mode}")
    if ref:
        args.append(ref)
    if paths:
        args.append("--")
        args.extend(paths)
    return args


def build_restore(
    paths: list[str],
    *,
    staged: bool = False,
    worktree: bool = False,
    source: str | None = None,
) -> list[str]:
    """Build ``git restore`` arguments.

    Args:
        paths: Paths to restore.
        staged: Restore the index (unstage).
        worktree: Restore working-tree files.
        source: Commit or ref to restore from.
    """
    if not paths:
        raise ValueError("At least one path is required.")
    if not staged and not worktree:
        worktree = True
    args = ["git", "restore"]
    if worktree:
        args.append("--worktree")
    if staged:
        args.append("--staged")
    if source:
        args.extend(["--source", source])
    args.append("--")
    args.extend(paths)
    return args


def build_config_set(
    key: str,
    value: str,
    *,
    scope: str = "local",
    repo_path: str | None = None,
) -> list[str]:
    """Build ``git config`` set arguments."""
    scope_flag = _resolve_scope_flag(scope)
    args = ["git"]
    if scope == "local" and repo_path:
        args.extend(["-C", repo_path])
    args.extend(["config", scope_flag, key, value])
    return args


def build_config_get(
    key: str,
    *,
    scope: str = "local",
    repo_path: str | None = None,
) -> list[str]:
    """Build ``git config --get`` arguments."""
    scope_flag = _resolve_scope_flag(scope)
    args = ["git"]
    if scope == "local" and repo_path:
        args.extend(["-C", repo_path])
    args.extend(["config", scope_flag, "--get", key])
    return args


def build_has_upstream() -> list[str]:
    """Build arguments to check if current branch has upstream tracking."""
    return ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]


# ── Parsers ────────────────────────────────────────────────────────

def parse_status(stdout: str) -> GitStatus:
    """Parse ``git status --porcelain=v1 --branch`` output.

    Args:
        stdout: Raw stdout from the git status command.

    Returns:
        Parsed :class:`GitStatus`.
    """
    lines = [line for line in stdout.split("\n") if line.rstrip()]
    if not lines:
        return GitStatus()

    status = GitStatus()

    branch_line = lines[0]
    if branch_line.startswith("## "):
        _parse_branch_line(branch_line[3:], status)

    for line in lines[1:]:
        if line.startswith("?? "):
            status.files.append(FileStatus(
                path=line[3:],
                index_status="?",
                work_tree_status="?",
            ))
            continue

        if len(line) < 4:
            continue

        idx = line[0]
        wt = line[1]
        path = line[3:]
        renamed_from = None
        if " -> " in path:
            renamed_from, path = path.split(" -> ", 1)

        status.files.append(FileStatus(
            path=path,
            index_status=idx,
            work_tree_status=wt,
            renamed_from=renamed_from,
        ))

    return status


def parse_branches(stdout: str) -> list[GitBranch]:
    """Parse ``git branch --format=%(refname:short)\\t%(HEAD)`` output.

    Args:
        stdout: Raw stdout from the git branch command.

    Returns:
        List of :class:`GitBranch`.
    """
    branches: list[GitBranch] = []
    for line in stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        name = parts[0]
        is_current = len(parts) > 1 and parts[1] == "*"
        branches.append(GitBranch(name=name, is_current=is_current))
    return branches


# ── Internal helpers ───────────────────────────────────────────────

def _resolve_scope_flag(scope: str) -> str:
    """Convert a scope name to a git config flag."""
    scope = scope.strip().lower()
    if scope == "local":
        return "--local"
    if scope == "global":
        return "--global"
    if scope == "system":
        return "--system"
    raise ValueError(
        "Git config scope must be one of: local, global, system."
    )


def _parse_branch_line(info: str, status: GitStatus) -> None:
    """Parse the ``## branch...upstream [ahead N, behind M]`` header."""
    ahead_start = info.find(" [")
    branch_part = info if ahead_start == -1 else info[:ahead_start]
    ahead_part = None if ahead_start == -1 else info[ahead_start + 2:-1]

    if branch_part.startswith("HEAD (detached at "):
        status.detached = True
        status.branch = branch_part[18:].rstrip(")")
    elif "detached" in branch_part or branch_part.startswith("HEAD"):
        status.detached = True
    elif "..." in branch_part:
        local, remote = branch_part.split("...", 1)
        status.branch = local or None
        status.upstream = remote or None
    else:
        name = (
            branch_part
            .replace("No commits yet on ", "")
            .replace("Initial commit on ", "")
        )
        status.branch = name or None

    if ahead_part:
        m = re.search(r"ahead (\d+)", ahead_part)
        if m:
            status.ahead = int(m.group(1))
        m = re.search(r"behind (\d+)", ahead_part)
        if m:
            status.behind = int(m.group(1))


def _derive_status(index_status: str, work_tree_status: str) -> str:
    """Derive a normalized status label from porcelain XY characters."""
    chars = {index_status, work_tree_status}
    if "U" in chars:
        return "conflict"
    if "R" in chars:
        return "renamed"
    if "C" in chars:
        return "copied"
    if "D" in chars:
        return "deleted"
    if "A" in chars:
        return "added"
    if "M" in chars:
        return "modified"
    if "T" in chars:
        return "typechange"
    if "?" in chars:
        return "untracked"
    return "unknown"
