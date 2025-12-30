"""Git MCP Server implementation.

This module implements an MCP server that exposes Git operations as tools.
It uses GitPython for Git operations and the MCP SDK for protocol handling.

The server exposes the following tools:
- git_status: Get the current repository status
- git_log: View commit history
- git_diff: Show changes between commits or working tree
- git_commit: Create a new commit
- git_branch_list: List all branches
- git_checkout: Switch to a different branch

Example usage:
    # Run as standalone server
    $ daw-git-mcp

    # Or programmatically
    from daw_mcp.git_mcp.server import create_server
    server = create_server("/path/to/repo")
"""

from __future__ import annotations

import logging
import os
from typing import Any

from git import InvalidGitRepositoryError, Repo
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def create_server(repo_path: str | None = None) -> FastMCP:
    """Create and configure the Git MCP server.

    Args:
        repo_path: Path to the Git repository. If None, uses current directory.

    Returns:
        Configured FastMCP server instance.
    """
    mcp = FastMCP("DAW Git MCP Server", json_response=True)

    # Default to current directory if no path specified
    working_dir = repo_path or os.getcwd()

    def get_repo() -> Repo:
        """Get the Git repository instance.

        Returns:
            Git Repo object.

        Raises:
            ValueError: If the path is not a valid Git repository.
        """
        try:
            return Repo(working_dir, search_parent_directories=True)
        except InvalidGitRepositoryError as e:
            raise ValueError(f"Not a valid Git repository: {working_dir}") from e

    @mcp.tool()
    def git_status() -> dict[str, Any]:
        """Get the current Git repository status.

        Returns information about:
        - Current branch name
        - Staged changes (files ready to commit)
        - Unstaged changes (modified files not yet staged)
        - Untracked files (new files not yet added)

        Returns:
            Dictionary with status information.
        """
        repo = get_repo()

        # Get current branch
        try:
            branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            branch = f"HEAD detached at {repo.head.commit.hexsha[:7]}"

        # Get staged files
        staged = [item.a_path for item in repo.index.diff("HEAD")]

        # Get unstaged (modified) files
        unstaged = [item.a_path for item in repo.index.diff(None)]

        # Get untracked files
        untracked = repo.untracked_files

        return {
            "branch": branch,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "is_dirty": repo.is_dirty(untracked_files=True),
        }

    @mcp.tool()
    def git_log(max_count: int = 10, branch: str | None = None) -> list[dict[str, Any]]:
        """Get commit history from the repository.

        Args:
            max_count: Maximum number of commits to return (default: 10).
            branch: Branch name to get history from. Uses current branch if None.

        Returns:
            List of commit dictionaries with sha, message, author, date.
        """
        repo = get_repo()

        # Determine which branch/ref to use
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

    @mcp.tool()
    def git_diff(
        ref1: str | None = None,
        ref2: str | None = None,
        staged: bool = False,
    ) -> str:
        """Show differences between commits, staging area, or working tree.

        Args:
            ref1: First reference (commit SHA, branch, tag). Defaults to HEAD.
            ref2: Second reference. If None, compares with working tree.
            staged: If True, show staged changes (ignores ref1/ref2).

        Returns:
            Diff output as a string.
        """
        repo = get_repo()

        if staged:
            # Show staged changes
            diff = repo.git.diff("--cached")
        elif ref1 and ref2:
            # Compare two refs
            diff = repo.git.diff(ref1, ref2)
        elif ref1:
            # Compare ref with working tree
            diff = repo.git.diff(ref1)
        else:
            # Show unstaged changes
            diff = repo.git.diff()

        return diff if diff else "No changes"

    @mcp.tool()
    def git_commit(message: str, add_all: bool = False) -> dict[str, Any]:
        """Create a new commit.

        Args:
            message: Commit message.
            add_all: If True, stage all modified files before committing.

        Returns:
            Dictionary with commit information.

        Raises:
            ValueError: If there are no changes to commit.
        """
        repo = get_repo()

        if add_all:
            repo.git.add("-A")

        # Check if there are staged changes
        if not repo.index.diff("HEAD"):
            raise ValueError("No changes staged for commit")

        # Create the commit
        commit = repo.index.commit(message)

        return {
            "sha": commit.hexsha,
            "short_sha": commit.hexsha[:7],
            "message": message,
            "author": str(commit.author),
        }

    @mcp.tool()
    def git_branch_list(include_remote: bool = False) -> dict[str, list[str]]:
        """List all branches in the repository.

        Args:
            include_remote: If True, also include remote tracking branches.

        Returns:
            Dictionary with 'local' and optionally 'remote' branch lists.
        """
        repo = get_repo()

        # Get local branches
        local_branches = [head.name for head in repo.heads]

        result: dict[str, list[str]] = {"local": local_branches}

        if include_remote:
            remote_branches = [ref.name for ref in repo.remote().refs]
            result["remote"] = remote_branches

        return result

    @mcp.tool()
    def git_checkout(branch: str, create: bool = False) -> dict[str, Any]:
        """Switch to a different branch.

        Args:
            branch: Name of the branch to switch to.
            create: If True, create the branch if it doesn't exist.

        Returns:
            Dictionary with checkout result.

        Raises:
            ValueError: If branch doesn't exist and create is False.
        """
        repo = get_repo()

        if create:
            # Create new branch from current HEAD
            new_branch = repo.create_head(branch)
            new_branch.checkout()
            return {
                "success": True,
                "branch": branch,
                "created": True,
            }
        else:
            # Check if branch exists
            if branch not in [h.name for h in repo.heads]:
                raise ValueError(f"Branch '{branch}' does not exist. Use create=True to create it.")

            repo.heads[branch].checkout()
            return {
                "success": True,
                "branch": branch,
                "created": False,
            }

    return mcp


def main() -> None:
    """Run the Git MCP server."""
    import sys

    # Get repo path from command line or environment
    repo_path = None
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    elif "GIT_MCP_REPO_PATH" in os.environ:
        repo_path = os.environ["GIT_MCP_REPO_PATH"]

    server = create_server(repo_path)

    # Run with stdio transport (default for CLI tools)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
