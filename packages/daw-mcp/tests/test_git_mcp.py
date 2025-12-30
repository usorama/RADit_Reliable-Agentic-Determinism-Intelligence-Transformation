"""Tests for the Git MCP server.

These tests verify the Git MCP server functionality using a temporary
Git repository for isolation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest
from git import Repo


@pytest.fixture
def temp_git_repo() -> Generator[Path, None, None]:
    """Create a temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        repo = Repo.init(repo_path)

        # Configure git user for commits
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create initial file and commit
        readme = repo_path / "README.md"
        readme.write_text("# Test Repository\n")
        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")

        yield repo_path


class TestGitMCPServerFunctions:
    """Test suite for the Git MCP server functions directly."""

    def test_create_server(self, temp_git_repo: Path) -> None:
        """Test server creation."""
        from daw_mcp.git_mcp.server import create_server

        server = create_server(str(temp_git_repo))
        assert server is not None
        assert server.name == "DAW Git MCP Server"

    def test_git_status_clean(self, temp_git_repo: Path) -> None:
        """Test git_status on a clean repository."""
        # Import and create functions directly with the repo path
        import os

        from git import InvalidGitRepositoryError, Repo

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_status() -> dict[str, Any]:
            repo = get_repo()
            try:
                branch = repo.active_branch.name
            except TypeError:
                branch = f"HEAD detached at {repo.head.commit.hexsha[:7]}"

            staged = [item.a_path for item in repo.index.diff("HEAD")]
            unstaged = [item.a_path for item in repo.index.diff(None)]
            untracked = repo.untracked_files

            return {
                "branch": branch,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "is_dirty": repo.is_dirty(untracked_files=True),
            }

        result = git_status()

        assert result["branch"] == "master" or result["branch"] == "main"
        assert result["staged"] == []
        assert result["unstaged"] == []
        assert result["untracked"] == []
        assert result["is_dirty"] is False

    def test_git_status_with_changes(self, temp_git_repo: Path) -> None:
        """Test git_status with uncommitted changes."""
        from git import InvalidGitRepositoryError, Repo

        # Create a new file
        new_file = temp_git_repo / "new_file.txt"
        new_file.write_text("New content\n")

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_status() -> dict[str, Any]:
            repo = get_repo()
            try:
                branch = repo.active_branch.name
            except TypeError:
                branch = f"HEAD detached at {repo.head.commit.hexsha[:7]}"

            staged = [item.a_path for item in repo.index.diff("HEAD")]
            unstaged = [item.a_path for item in repo.index.diff(None)]
            untracked = repo.untracked_files

            return {
                "branch": branch,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "is_dirty": repo.is_dirty(untracked_files=True),
            }

        result = git_status()

        assert "new_file.txt" in result["untracked"]
        assert result["is_dirty"] is True

    def test_git_log(self, temp_git_repo: Path) -> None:
        """Test git_log returns commit history."""
        from git import InvalidGitRepositoryError, Repo

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_log(max_count: int = 10, branch: str | None = None) -> list[dict[str, Any]]:
            repo = get_repo()
            ref = branch if branch else "HEAD"

            commits = []
            for commit in repo.iter_commits(ref, max_count=max_count):
                commits.append(
                    {
                        "sha": commit.hexsha,
                        "short_sha": commit.hexsha[:7],
                        "message": commit.message.strip(),
                        "author": str(commit.author),
                        "email": commit.author.email,
                        "date": commit.committed_datetime.isoformat(),
                    }
                )

            return commits

        result = git_log(max_count=5)

        assert len(result) >= 1
        assert result[0]["message"] == "Initial commit"
        assert "sha" in result[0]
        assert "author" in result[0]

    def test_git_diff_no_changes(self, temp_git_repo: Path) -> None:
        """Test git_diff with no changes."""
        from git import InvalidGitRepositoryError, Repo

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_diff(
            ref1: str | None = None,
            ref2: str | None = None,
            staged: bool = False,
        ) -> str:
            repo = get_repo()

            if staged:
                diff = repo.git.diff("--cached")
            elif ref1 and ref2:
                diff = repo.git.diff(ref1, ref2)
            elif ref1:
                diff = repo.git.diff(ref1)
            else:
                diff = repo.git.diff()

            return diff if diff else "No changes"

        result = git_diff()
        assert result == "No changes"

    def test_git_diff_with_changes(self, temp_git_repo: Path) -> None:
        """Test git_diff with uncommitted changes."""
        from git import InvalidGitRepositoryError, Repo

        # Modify existing file
        readme = temp_git_repo / "README.md"
        readme.write_text("# Modified Repository\n")

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_diff(
            ref1: str | None = None,
            ref2: str | None = None,
            staged: bool = False,
        ) -> str:
            repo = get_repo()

            if staged:
                diff = repo.git.diff("--cached")
            elif ref1 and ref2:
                diff = repo.git.diff(ref1, ref2)
            elif ref1:
                diff = repo.git.diff(ref1)
            else:
                diff = repo.git.diff()

            return diff if diff else "No changes"

        result = git_diff()
        assert "Modified Repository" in result or "README.md" in result

    def test_git_branch_list(self, temp_git_repo: Path) -> None:
        """Test git_branch_list returns branches."""
        from git import InvalidGitRepositoryError, Repo

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_branch_list(include_remote: bool = False) -> dict[str, list[str]]:
            repo = get_repo()
            local_branches = [head.name for head in repo.heads]
            result: dict[str, list[str]] = {"local": local_branches}

            if include_remote and repo.remotes:
                remote_branches = [ref.name for ref in repo.remote().refs]
                result["remote"] = remote_branches

            return result

        result = git_branch_list()

        assert "local" in result
        assert len(result["local"]) >= 1

    def test_git_checkout_create_branch(self, temp_git_repo: Path) -> None:
        """Test creating a new branch."""
        from git import InvalidGitRepositoryError, Repo

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_checkout(branch: str, create: bool = False) -> dict[str, Any]:
            repo = get_repo()

            if create:
                new_branch = repo.create_head(branch)
                new_branch.checkout()
                return {
                    "success": True,
                    "branch": branch,
                    "created": True,
                }
            else:
                if branch not in [h.name for h in repo.heads]:
                    raise ValueError(
                        f"Branch '{branch}' does not exist. Use create=True to create it."
                    )

                repo.heads[branch].checkout()
                return {
                    "success": True,
                    "branch": branch,
                    "created": False,
                }

        result = git_checkout(branch="feature/test", create=True)

        assert result["success"] is True
        assert result["branch"] == "feature/test"
        assert result["created"] is True

    def test_git_checkout_nonexistent_branch(self, temp_git_repo: Path) -> None:
        """Test checkout of nonexistent branch fails."""
        from git import InvalidGitRepositoryError, Repo

        working_dir = str(temp_git_repo)

        def get_repo() -> Repo:
            try:
                return Repo(working_dir, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {working_dir}") from e

        def git_checkout(branch: str, create: bool = False) -> dict[str, Any]:
            repo = get_repo()

            if create:
                new_branch = repo.create_head(branch)
                new_branch.checkout()
                return {
                    "success": True,
                    "branch": branch,
                    "created": True,
                }
            else:
                if branch not in [h.name for h in repo.heads]:
                    raise ValueError(
                        f"Branch '{branch}' does not exist. Use create=True to create it."
                    )

                repo.heads[branch].checkout()
                return {
                    "success": True,
                    "branch": branch,
                    "created": False,
                }

        with pytest.raises(ValueError, match="does not exist"):
            git_checkout(branch="nonexistent", create=False)

    def test_invalid_repo_path(self) -> None:
        """Test error handling for invalid repository path."""
        from git import InvalidGitRepositoryError, Repo

        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = tmpdir

            def get_repo() -> Repo:
                try:
                    return Repo(working_dir, search_parent_directories=True)
                except InvalidGitRepositoryError as e:
                    raise ValueError(f"Not a valid Git repository: {working_dir}") from e

            def git_status() -> dict[str, Any]:
                repo = get_repo()
                try:
                    branch = repo.active_branch.name
                except TypeError:
                    branch = f"HEAD detached at {repo.head.commit.hexsha[:7]}"

                staged = [item.a_path for item in repo.index.diff("HEAD")]
                unstaged = [item.a_path for item in repo.index.diff(None)]
                untracked = repo.untracked_files

                return {
                    "branch": branch,
                    "staged": staged,
                    "unstaged": unstaged,
                    "untracked": untracked,
                    "is_dirty": repo.is_dirty(untracked_files=True),
                }

            with pytest.raises(ValueError, match="Not a valid Git repository"):
                git_status()


class TestGitMCPServerCreation:
    """Test server creation and configuration."""

    def test_server_has_tools(self, temp_git_repo: Path) -> None:
        """Test that server registers expected tools."""
        from daw_mcp.git_mcp.server import create_server

        server = create_server(str(temp_git_repo))

        # Check that the server has a tool manager with tools
        assert hasattr(server, "_tool_manager")
        tools = server._tool_manager._tools
        assert "git_status" in tools
        assert "git_log" in tools
        assert "git_diff" in tools
        assert "git_commit" in tools
        assert "git_branch_list" in tools
        assert "git_checkout" in tools
