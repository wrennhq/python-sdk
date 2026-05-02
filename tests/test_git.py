from __future__ import annotations

import json

import pytest
import respx

from wrenn._git import (
    AsyncGit,
    FileStatus,
    Git,
    GitAuthError,
    GitCommandError,
    GitError,
    GitStatus,
    _check_result,
    _derive_repo_dir,
)
from wrenn._git._auth import (
    build_credential_approve_cmd,
    embed_credentials,
    is_auth_error,
    strip_credentials,
)
from wrenn._git._cmd import (
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
from wrenn.commands import CommandResult

BASE = "https://app.wrenn.dev/api"
CAPSULE_ID = "cl-test123"
EXEC_URL = f"{BASE}/v1/capsules/{CAPSULE_ID}/exec"


# ── Helpers ────────────────────────────────────────────────────────


def _exec_response(
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    duration_ms: int = 10,
) -> dict:
    """Build a mock exec API response body."""
    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
    }


def _make_git(respx_mock=None) -> Git:
    """Create a Git instance bound to a test capsule."""
    from wrenn.client import WrennClient

    client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
    return Git(CAPSULE_ID, client.http)


def _make_async_git() -> AsyncGit:
    """Create an AsyncGit instance bound to a test capsule."""
    from wrenn.client import AsyncWrennClient

    client = AsyncWrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
    return AsyncGit(CAPSULE_ID, client.http)


# ══════════════════════════════════════════════════════════════════
# Pure function tests — no I/O, no mocking
# ══════════════════════════════════════════════════════════════════


class TestBuildClone:
    def test_basic(self):
        args = build_clone("https://github.com/user/repo.git")
        assert args == ["git", "clone", "https://github.com/user/repo.git"]

    def test_with_dest(self):
        args = build_clone("https://github.com/user/repo.git", "/tmp/repo")
        assert args[-1] == "/tmp/repo"

    def test_with_branch(self):
        args = build_clone("https://github.com/user/repo.git", branch="main")
        assert "--branch" in args
        assert "main" in args
        assert "--single-branch" in args

    def test_with_depth(self):
        args = build_clone("https://github.com/user/repo.git", depth=1)
        assert "--depth" in args
        assert "1" in args

    def test_all_options(self):
        args = build_clone(
            "https://github.com/user/repo.git",
            "/tmp/repo",
            branch="dev",
            depth=5,
        )
        assert args == [
            "git",
            "clone",
            "--branch",
            "dev",
            "--single-branch",
            "--depth",
            "5",
            "https://github.com/user/repo.git",
            "/tmp/repo",
        ]


class TestBuildInit:
    def test_basic(self):
        assert build_init("/repo") == ["git", "init", "/repo"]

    def test_bare(self):
        args = build_init("/repo", bare=True)
        assert "--bare" in args

    def test_initial_branch(self):
        args = build_init("/repo", initial_branch="main")
        assert "--initial-branch" in args
        assert "main" in args


class TestBuildAdd:
    def test_default(self):
        assert build_add() == ["git", "add", "."]

    def test_all(self):
        assert build_add(all=True) == ["git", "add", "-A"]

    def test_specific_files(self):
        args = build_add(["file1.py", "file2.py"])
        assert args == ["git", "add", "--", "file1.py", "file2.py"]


class TestBuildCommit:
    def test_basic(self):
        args = build_commit("initial commit")
        assert args == ["git", "commit", "-m", "initial commit"]

    def test_allow_empty(self):
        args = build_commit("empty", allow_empty=True)
        assert "--allow-empty" in args

    def test_author_override(self):
        args = build_commit("msg", author_name="Bob", author_email="bob@test.com")
        assert "-c" in args
        assert "user.name=Bob" in args
        assert "user.email=bob@test.com" in args


class TestBuildPush:
    def test_basic(self):
        assert build_push() == ["git", "push", "origin"]

    def test_with_branch(self):
        args = build_push("origin", "main")
        assert args == ["git", "push", "origin", "main"]

    def test_force(self):
        args = build_push(force=True)
        assert "--force" in args

    def test_set_upstream(self):
        args = build_push(set_upstream=True)
        assert "--set-upstream" in args


class TestBuildPull:
    def test_basic(self):
        assert build_pull() == ["git", "pull", "origin"]

    def test_rebase(self):
        args = build_pull(rebase=True)
        assert "--rebase" in args

    def test_ff_only(self):
        args = build_pull(ff_only=True)
        assert "--ff-only" in args

    def test_with_branch(self):
        args = build_pull("upstream", "feature")
        assert args == ["git", "pull", "upstream", "feature"]


class TestBuildStatus:
    def test_args(self):
        assert build_status() == ["git", "status", "--porcelain=v1", "--branch"]


class TestBuildBranches:
    def test_args(self):
        assert build_branches() == [
            "git",
            "branch",
            "--format=%(refname:short)\t%(HEAD)",
        ]


class TestBuildBranchOps:
    def test_create(self):
        assert build_create_branch("feat") == ["git", "checkout", "-b", "feat"]

    def test_create_with_start_point(self):
        args = build_create_branch("feat", start_point="abc123")
        assert args == ["git", "checkout", "-b", "feat", "abc123"]

    def test_checkout(self):
        assert build_checkout("main") == ["git", "checkout", "main"]

    def test_delete(self):
        assert build_delete_branch("old") == ["git", "branch", "-d", "old"]

    def test_force_delete(self):
        assert build_delete_branch("old", force=True) == ["git", "branch", "-D", "old"]


class TestBuildRemote:
    def test_add(self):
        args = build_remote_add("origin", "https://example.com/repo.git")
        assert args == [
            "git",
            "remote",
            "add",
            "origin",
            "https://example.com/repo.git",
        ]

    def test_add_with_fetch(self):
        args = build_remote_add("origin", "https://example.com/repo.git", fetch=True)
        assert "-f" in args

    def test_get_url(self):
        assert build_remote_get_url("origin") == ["git", "remote", "get-url", "origin"]

    def test_set_url(self):
        args = build_remote_set_url("origin", "https://new.url/repo.git")
        assert args == [
            "git",
            "remote",
            "set-url",
            "origin",
            "https://new.url/repo.git",
        ]


class TestBuildReset:
    def test_basic(self):
        assert build_reset() == ["git", "reset"]

    def test_hard(self):
        args = build_reset(mode="hard")
        assert args == ["git", "reset", "--hard"]

    def test_with_ref(self):
        args = build_reset(mode="soft", ref="HEAD~1")
        assert args == ["git", "reset", "--soft", "HEAD~1"]

    def test_with_paths(self):
        args = build_reset(paths=["file.py"])
        assert args == ["git", "reset", "--", "file.py"]

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="Reset mode"):
            build_reset(mode="invalid")


class TestBuildRestore:
    def test_basic(self):
        args = build_restore(["file.py"])
        assert args == ["git", "restore", "--worktree", "--", "file.py"]

    def test_staged(self):
        args = build_restore(["file.py"], staged=True)
        assert "--staged" in args

    def test_both(self):
        args = build_restore(["file.py"], staged=True, worktree=True)
        assert "--staged" in args
        assert "--worktree" in args

    def test_with_source(self):
        args = build_restore(["file.py"], source="HEAD~1")
        assert "--source" in args
        assert "HEAD~1" in args

    def test_empty_paths_raises(self):
        with pytest.raises(ValueError, match="At least one path"):
            build_restore([])


class TestBuildConfig:
    def test_set_local(self):
        args = build_config_set("user.name", "Bob", scope="local", repo_path="/repo")
        assert args == ["git", "-C", "/repo", "config", "--local", "user.name", "Bob"]

    def test_set_global(self):
        args = build_config_set("user.name", "Bob", scope="global")
        assert args == ["git", "config", "--global", "user.name", "Bob"]

    def test_get_global(self):
        args = build_config_get("user.name", scope="global")
        assert args == ["git", "config", "--global", "--get", "user.name"]

    def test_invalid_scope(self):
        with pytest.raises(ValueError, match="scope"):
            build_config_set("key", "val", scope="invalid")


# ── Parser tests ───────────────────────────────────────────────────


class TestParseStatus:
    def test_empty(self):
        status = parse_status("")
        assert status.branch is None
        assert status.is_clean is True
        assert status.files == []

    def test_clean_repo(self):
        status = parse_status("## main...origin/main\n")
        assert status.branch == "main"
        assert status.upstream == "origin/main"
        assert status.is_clean is True

    def test_modified_file(self):
        status = parse_status("## main\n M file.py\n")
        assert len(status.files) == 1
        f = status.files[0]
        assert f.path == "file.py"
        assert f.work_tree_status == "M"
        assert f.status == "modified"
        assert f.staged is False

    def test_staged_file(self):
        status = parse_status("## main\nM  file.py\n")
        f = status.files[0]
        assert f.index_status == "M"
        assert f.staged is True

    def test_untracked(self):
        status = parse_status("## main\n?? new.txt\n")
        f = status.files[0]
        assert f.status == "untracked"
        assert f.staged is False

    def test_renamed(self):
        status = parse_status("## main\nR  old.py -> new.py\n")
        f = status.files[0]
        assert f.status == "renamed"
        assert f.path == "new.py"
        assert f.renamed_from == "old.py"

    def test_ahead_behind(self):
        status = parse_status("## main...origin/main [ahead 3, behind 1]\n")
        assert status.ahead == 3
        assert status.behind == 1

    def test_ahead_only(self):
        status = parse_status("## main...origin/main [ahead 2]\n")
        assert status.ahead == 2
        assert status.behind == 0

    def test_detached_head(self):
        status = parse_status("## HEAD (detached at abc1234)\n")
        assert status.detached is True
        assert status.branch == "abc1234"

    def test_no_commits_yet(self):
        status = parse_status("## No commits yet on main\n")
        assert status.branch == "main"

    def test_multiple_files(self):
        output = "## dev\nM  a.py\n M b.py\n?? c.txt\nA  d.py\nD  e.py\n"
        status = parse_status(output)
        assert len(status.files) == 5
        assert status.has_staged is True
        assert status.has_untracked is True

    def test_has_conflicts(self):
        status = parse_status("## main\nUU conflict.py\n")
        assert status.has_conflicts is True
        assert status.files[0].status == "conflict"


class TestParseBranches:
    def test_single_branch(self):
        branches = parse_branches("main\t*\n")
        assert len(branches) == 1
        assert branches[0].name == "main"
        assert branches[0].is_current is True

    def test_multiple(self):
        branches = parse_branches("main\t*\ndev\t \nfeature\t \n")
        assert len(branches) == 3
        current = [b for b in branches if b.is_current]
        assert len(current) == 1
        assert current[0].name == "main"

    def test_empty(self):
        branches = parse_branches("")
        assert branches == []

    def test_no_current(self):
        branches = parse_branches("main\t \ndev\t \n")
        assert all(not b.is_current for b in branches)


# ── Auth helper tests ──────────────────────────────────────────────


class TestEmbedCredentials:
    def test_basic(self):
        url = embed_credentials("https://github.com/user/repo.git", "user", "token")
        assert url == "https://user:token@github.com/user/repo.git"

    def test_with_port(self):
        url = embed_credentials("https://git.example.com:8443/repo.git", "u", "p")
        assert "u:p@git.example.com:8443" in url

    def test_ssh_raises(self):
        with pytest.raises(ValueError, match="http"):
            embed_credentials("git@github.com:user/repo.git", "u", "p")


class TestStripCredentials:
    def test_basic(self):
        url = strip_credentials("https://user:token@github.com/user/repo.git")
        assert url == "https://github.com/user/repo.git"

    def test_no_credentials(self):
        url = "https://github.com/user/repo.git"
        assert strip_credentials(url) == url

    def test_ssh_unchanged(self):
        url = "git@github.com:user/repo.git"
        assert strip_credentials(url) == url


class TestIsAuthError:
    @pytest.mark.parametrize(
        "msg",
        [
            "fatal: Authentication failed for 'https://...'",
            "fatal: could not read Username",
            "remote: Invalid username or password",
            "fatal: terminal prompts disabled",
            "Permission denied (publickey)",
        ],
    )
    def test_auth_patterns(self, msg):
        assert is_auth_error(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "fatal: repository 'https://...' not found",
            "error: pathspec 'foo' did not match any file(s)",
            "",
        ],
    )
    def test_non_auth_patterns(self, msg):
        assert is_auth_error(msg) is False


class TestBuildCredentialApproveCmd:
    def test_basic(self):
        cmd = build_credential_approve_cmd("user", "token123", "github.com", "https")
        assert "git credential approve" in cmd
        assert "protocol=https" in cmd
        assert "host=github.com" in cmd
        assert "username=user" in cmd
        assert "password=token123" in cmd

    def test_newline_rejected(self):
        with pytest.raises(ValueError, match="newline"):
            build_credential_approve_cmd("user", "tok\nen", "github.com", "https")


# ── _check_result tests ───────────────────────────────────────────


class TestCheckResult:
    def test_success(self):
        result = CommandResult(stdout="ok\n", stderr="", exit_code=0)
        _check_result(result, op="test")  # should not raise

    def test_generic_failure(self):
        result = CommandResult(stdout="", stderr="fatal: bad thing", exit_code=1)
        with pytest.raises(GitCommandError) as exc_info:
            _check_result(result, op="push")
        assert exc_info.value.exit_code == 1
        assert "fatal: bad thing" in exc_info.value.message

    def test_auth_failure(self):
        result = CommandResult(
            stdout="",
            stderr="fatal: Authentication failed for 'https://...'",
            exit_code=128,
        )
        with pytest.raises(GitAuthError) as exc_info:
            _check_result(result, op="clone")
        assert "authentication failed" in exc_info.value.message
        assert exc_info.value.exit_code == 128

    def test_fallback_message(self):
        result = CommandResult(stdout="", stderr="", exit_code=42)
        with pytest.raises(GitCommandError, match="git test failed"):
            _check_result(result, op="test")


# ── _derive_repo_dir tests ────────────────────────────────────────


class TestDeriveRepoDir:
    def test_basic(self):
        assert _derive_repo_dir("https://github.com/user/repo.git") == "repo"

    def test_no_git_suffix(self):
        assert _derive_repo_dir("https://github.com/user/repo") == "repo"

    def test_trailing_slash(self):
        assert _derive_repo_dir("https://github.com/user/repo.git/") == "repo"

    def test_ssh_returns_none(self):
        assert _derive_repo_dir("git@github.com:user/repo.git") is None

    def test_empty_path(self):
        assert _derive_repo_dir("https://github.com") is None


# ── FileStatus property tests ─────────────────────────────────────


class TestFileStatus:
    def test_staged_property(self):
        f = FileStatus(path="a.py", index_status="M", work_tree_status=" ")
        assert f.staged is True

    def test_not_staged(self):
        f = FileStatus(path="a.py", index_status=" ", work_tree_status="M")
        assert f.staged is False

    def test_untracked_not_staged(self):
        f = FileStatus(path="a.py", index_status="?", work_tree_status="?")
        assert f.staged is False

    def test_status_property(self):
        cases = [
            (("U", " "), "conflict"),
            (("R", " "), "renamed"),
            (("C", " "), "copied"),
            (("D", " "), "deleted"),
            (("A", " "), "added"),
            (("M", " "), "modified"),
            (("T", " "), "typechange"),
            (("?", "?"), "untracked"),
            ((" ", " "), "unknown"),
        ]
        for (idx, wt), expected in cases:
            f = FileStatus(path="x", index_status=idx, work_tree_status=wt)
            assert f.status == expected, f"Expected {expected} for ({idx!r}, {wt!r})"


# ── GitStatus property tests ──────────────────────────────────────


class TestGitStatus:
    def test_is_clean(self):
        s = GitStatus()
        assert s.is_clean is True

    def test_has_staged(self):
        s = GitStatus(
            files=[
                FileStatus(path="a.py", index_status="M", work_tree_status=" "),
            ]
        )
        assert s.has_staged is True

    def test_has_untracked(self):
        s = GitStatus(
            files=[
                FileStatus(path="a.py", index_status="?", work_tree_status="?"),
            ]
        )
        assert s.has_untracked is True

    def test_has_conflicts(self):
        s = GitStatus(
            files=[
                FileStatus(path="a.py", index_status="U", work_tree_status="U"),
            ]
        )
        assert s.has_conflicts is True


# ══════════════════════════════════════════════════════════════════
# Integration tests — Git class with mocked HTTP
# ══════════════════════════════════════════════════════════════════


class TestGitInit:
    @respx.mock
    def test_init(self):
        respx.post(EXEC_URL).respond(
            200,
            json=_exec_response(
                stdout="Initialized empty Git repository in /repo/.git/\n"
            ),
        )
        git = _make_git()
        result = git.init("/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_init_failure(self):
        respx.post(EXEC_URL).respond(
            200,
            json=_exec_response(stderr="fatal: cannot mkdir /readonly", exit_code=128),
        )
        git = _make_git()
        with pytest.raises(GitCommandError):
            git.init("/readonly")


class TestGitClone:
    @respx.mock
    def test_clone_basic(self):
        route = respx.post(EXEC_URL).respond(
            200, json=_exec_response(stderr="Cloning into 'repo'...\n")
        )
        git = _make_git()
        result = git.clone("https://github.com/user/repo.git")
        assert result.exit_code == 0
        req_body = route.calls[0].request.content.decode()
        assert "git clone" in req_body

    @respx.mock
    def test_clone_auth_failure(self):
        respx.post(EXEC_URL).respond(
            200,
            json=_exec_response(
                stderr="fatal: Authentication failed for 'https://...'",
                exit_code=128,
            ),
        )
        git = _make_git()
        with pytest.raises(GitAuthError):
            git.clone("https://github.com/private/repo.git")

    def test_clone_password_without_username(self):
        git = _make_git()
        with pytest.raises(ValueError, match="Username is required"):
            git.clone("https://github.com/user/repo.git", password="token")

    @respx.mock
    def test_clone_with_credentials_strips(self):
        # First call: clone. Second call: set-url to strip creds.
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        git.clone(
            "https://github.com/user/repo.git",
            dest="/tmp/repo",
            username="user",
            password="token",
        )
        # Should have made 2 calls: clone + set-url
        assert len(respx.calls) == 2


class TestGitAdd:
    @respx.mock
    def test_add_all(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.add(all=True, cwd="/repo")
        assert result.exit_code == 0


class TestGitCommit:
    @respx.mock
    def test_commit(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="[main abc1234] initial commit\n")
        )
        git = _make_git()
        result = git.commit("initial commit", cwd="/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_commit_nothing_to_commit(self):
        respx.post(EXEC_URL).respond(
            200,
            json=_exec_response(
                stdout="nothing to commit, working tree clean\n",
                stderr="",
                exit_code=1,
            ),
        )
        git = _make_git()
        with pytest.raises(GitCommandError):
            git.commit("empty", cwd="/repo")


class TestGitPushPull:
    @respx.mock
    def test_push(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.push(cwd="/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_pull(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.pull(cwd="/repo")
        assert result.exit_code == 0


class TestGitStatusCommand:
    @respx.mock
    def test_status(self):
        respx.post(EXEC_URL).respond(
            200,
            json=_exec_response(
                stdout="## main...origin/main [ahead 1]\n M file.py\n?? new.txt\n"
            ),
        )
        git = _make_git()
        status = git.status(cwd="/repo")
        assert isinstance(status, GitStatus)
        assert status.branch == "main"
        assert status.ahead == 1
        assert len(status.files) == 2


class TestGitBranches:
    @respx.mock
    def test_branches(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="main\t*\ndev\t \n")
        )
        git = _make_git()
        branches = git.branches(cwd="/repo")
        assert len(branches) == 2
        assert branches[0].name == "main"
        assert branches[0].is_current is True

    @respx.mock
    def test_create_branch(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stderr="Switched to a new branch 'feat'\n")
        )
        git = _make_git()
        result = git.create_branch("feat", cwd="/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_checkout_branch(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stderr="Switched to branch 'main'\n")
        )
        git = _make_git()
        result = git.checkout_branch("main", cwd="/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_delete_branch(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="Deleted branch old (was abc1234).\n")
        )
        git = _make_git()
        result = git.delete_branch("old", cwd="/repo")
        assert result.exit_code == 0


class TestGitRemote:
    @respx.mock
    def test_remote_add(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.remote_add("origin", "https://example.com/repo.git", cwd="/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_remote_get(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="https://example.com/repo.git\n")
        )
        git = _make_git()
        url = git.remote_get("origin", cwd="/repo")
        assert url == "https://example.com/repo.git"

    @respx.mock
    def test_remote_get_not_found(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stderr="fatal: No such remote 'nope'", exit_code=2)
        )
        git = _make_git()
        url = git.remote_get("nope", cwd="/repo")
        assert url is None


class TestGitResetRestore:
    @respx.mock
    def test_reset(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.reset(mode="hard", ref="HEAD~1", cwd="/repo")
        assert result.exit_code == 0

    @respx.mock
    def test_restore(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.restore(["file.py"], staged=True, cwd="/repo")
        assert result.exit_code == 0


class TestGitConfig:
    @respx.mock
    def test_set_config(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        result = git.set_config("user.name", "Bob", scope="global")
        assert result.exit_code == 0

    @respx.mock
    def test_get_config(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response(stdout="Bob\n"))
        git = _make_git()
        val = git.get_config("user.name", scope="global")
        assert val == "Bob"

    @respx.mock
    def test_get_config_not_set(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response(stderr="", exit_code=1))
        git = _make_git()
        val = git.get_config("nonexistent.key", scope="global")
        assert val is None

    @respx.mock
    def test_configure_user(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        git.configure_user("Bob", "bob@test.com", scope="global")
        assert len(respx.calls) == 2  # user.name + user.email

    def test_configure_user_empty_name(self):
        git = _make_git()
        with pytest.raises(ValueError, match="Both name and email"):
            git.configure_user("", "bob@test.com")


class TestDangerouslyAuthenticate:
    @respx.mock
    def test_authenticate(self):
        respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        git.dangerously_authenticate("user", "token123")
        # Should make 2 calls: config set + credential approve
        assert len(respx.calls) == 2

    def test_empty_credentials(self):
        git = _make_git()
        with pytest.raises(ValueError, match="Both username and password"):
            git.dangerously_authenticate("", "token")


# ── Exception hierarchy tests ─────────────────────────────────────


class TestExceptionHierarchy:
    def test_git_command_error_is_git_error(self):
        assert issubclass(GitCommandError, GitError)

    def test_git_auth_error_is_git_error(self):
        assert issubclass(GitAuthError, GitError)

    def test_git_error_is_not_wrenn_error(self):
        from wrenn.exceptions import WrennError

        assert not issubclass(GitError, WrennError)

    def test_error_attributes(self):
        err = GitCommandError("msg", stderr="err output", exit_code=42)
        assert err.message == "msg"
        assert err.stderr == "err output"
        assert err.exit_code == 42
        assert str(err) == "msg"


# ── Capsule wiring tests ──────────────────────────────────────────


class TestCapsuleWiring:
    @respx.mock
    def test_capsule_has_git(self):
        from wrenn.capsule import Capsule

        respx.post(f"{BASE}/v1/capsules").respond(
            201, json={"id": "cl-1", "status": "pending"}
        )
        cap = Capsule(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        assert hasattr(cap, "git")
        assert isinstance(cap.git, Git)


# ── Async tests ───────────────────────────────────────────────────


class TestAsyncGit:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_init(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="Initialized empty Git repository\n")
        )
        git = _make_async_git()
        result = await git.init("/repo")
        assert result.exit_code == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_status(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="## main\n M file.py\n")
        )
        git = _make_async_git()
        status = await git.status(cwd="/repo")
        assert isinstance(status, GitStatus)
        assert status.branch == "main"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_clone_auth_error(self):
        respx.post(EXEC_URL).respond(
            200,
            json=_exec_response(stderr="fatal: Authentication failed", exit_code=128),
        )
        git = _make_async_git()
        with pytest.raises(GitAuthError):
            await git.clone("https://github.com/private/repo.git")

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_commit(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="[main abc1234] test\n")
        )
        git = _make_async_git()
        result = await git.commit("test", cwd="/repo")
        assert result.exit_code == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_branches(self):
        respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="main\t*\ndev\t \n")
        )
        git = _make_async_git()
        branches = await git.branches(cwd="/repo")
        assert len(branches) == 2


# ════════════════════════════════��═════════════════════════════════
# Command payload tests — verify /bin/sh -c wrapping
# ════════════════════════════���══════════════════════���══════════════


class TestCommandPayloadWrapping:
    """Verify that Commands.run sends cmd=/bin/sh args=['-c', cmd_string]
    so the server-side wrapper expands "${@}" into proper argv."""

    @respx.mock
    def test_simple_command(self):
        route = respx.post(EXEC_URL).respond(
            200, json=_exec_response(stdout="hello world\n")
        )
        git = _make_git()
        git.init("/repo")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", git_cmd_from_body(body)]
        # args[1] should contain the actual git command
        assert body["args"][0] == "-c"
        assert "git" in body["args"][1]

    @respx.mock
    def test_command_with_pipes(self):
        """Pipes and redirects work because /bin/sh interprets them."""
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json=_exec_response(stdout="3\n"))
        commands.run("cat /etc/passwd | wc -l")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "cat /etc/passwd | wc -l"]

    @respx.mock
    def test_command_with_semicolons(self):
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json=_exec_response())
        commands.run("cd /tmp; ls -la && echo done")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "cd /tmp; ls -la && echo done"]

    @respx.mock
    def test_command_with_env_vars(self):
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json=_exec_response())
        commands.run("FOO=bar echo $FOO")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "FOO=bar echo $FOO"]

    @respx.mock
    def test_command_with_subshell(self):
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json=_exec_response())
        commands.run("echo $(date +%s)")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "echo $(date +%s)"]

    @respx.mock
    def test_command_with_quotes_and_spaces(self):
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json=_exec_response())
        commands.run("""echo "hello 'world'" | grep -o "'[^']*'" """)
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"][0] == "-c"
        # The command string is passed verbatim — shell interprets it
        assert "hello 'world'" in body["args"][1]

    @respx.mock
    def test_heredoc_style_command(self):
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json=_exec_response())
        commands.run("python3 -c 'import sys; print(sys.version)'")
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "python3 -c 'import sys; print(sys.version)'"]

    @respx.mock
    def test_git_shlex_joined_command(self):
        """Git module uses shlex.join — verify it passes through correctly."""
        route = respx.post(EXEC_URL).respond(200, json=_exec_response())
        git = _make_git()
        git.clone("https://github.com/user/repo.git", "/tmp/repo", depth=1)
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"][0] == "-c"
        # shlex.join produces: git clone --depth 1 https://... /tmp/repo
        shell_cmd = body["args"][1]
        assert "git" in shell_cmd
        assert "clone" in shell_cmd
        assert "--depth" in shell_cmd
        assert "https://github.com/user/repo.git" in shell_cmd

    @respx.mock
    def test_background_command_also_wrapped(self):
        from wrenn.client import WrennClient
        from wrenn.commands import Commands

        client = WrennClient(api_key="wrn_test1234567890abcdef12345678", base_url=BASE)
        commands = Commands(CAPSULE_ID, client.http)

        route = respx.post(EXEC_URL).respond(200, json={"pid": 42, "tag": "bg-1"})
        commands.run("tail -f /var/log/syslog", background=True)
        body = json.loads(route.calls[0].request.content)
        assert body["cmd"] == "/bin/sh"
        assert body["args"] == ["-c", "tail -f /var/log/syslog"]
        assert body["background"] is True


def git_cmd_from_body(body: dict) -> str:
    """Extract the shell command string from a wrapped payload."""
    assert body["cmd"] == "/bin/sh"
    assert body["args"][0] == "-c"
    return body["args"][1]
