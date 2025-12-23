"""
Git integration for automatic metadata population.

Automatically detects and populates git context (branch, commit hash)
in todo metadata when operating within a git repository.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_git_root(path: Optional[str] = None) -> Optional[Path]:
    """
    Find the root directory of the git repository.

    Args:
        path: Starting path to search from (defaults to current directory)

    Returns:
        Path to git root, or None if not in a git repository
    """
    try:
        search_path = Path(path) if path else Path.cwd()
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=search_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Not in git repository: {e}")
        return None


def get_current_branch(path: Optional[str] = None) -> Optional[str]:
    """
    Get the current git branch name.

    Args:
        path: Path to check (defaults to current directory)

    Returns:
        Branch name, or None if not in a git repository or detached HEAD
    """
    try:
        search_path = Path(path) if path else Path.cwd()
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=search_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            # Return None for detached HEAD state
            return None if branch == "HEAD" else branch
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Could not get git branch: {e}")
        return None


def get_current_commit_hash(path: Optional[str] = None, short: bool = True) -> Optional[str]:
    """
    Get the current git commit hash.

    Args:
        path: Path to check (defaults to current directory)
        short: Return short hash (7 chars) instead of full hash

    Returns:
        Commit hash, or None if not in a git repository
    """
    try:
        search_path = Path(path) if path else Path.cwd()
        cmd = ["git", "rev-parse"]
        if short:
            cmd.append("--short")
        cmd.append("HEAD")

        result = subprocess.run(
            cmd,
            cwd=search_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Could not get git commit hash: {e}")
        return None


def get_git_metadata(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all available git metadata for the current context.

    Args:
        path: Path to check (defaults to current directory)

    Returns:
        Dictionary with git metadata (branch, commit_hash, git_root)
        Returns empty dict if not in a git repository
    """
    git_root = get_git_root(path)
    if not git_root:
        return {}

    metadata = {}

    branch = get_current_branch(path)
    if branch:
        metadata["branch"] = branch

    commit_hash = get_current_commit_hash(path, short=True)
    if commit_hash:
        metadata["commit_hash"] = commit_hash

    return metadata


def enrich_metadata_with_git(metadata: Optional[Dict[str, Any]] = None,
                             path: Optional[str] = None,
                             auto_detect: bool = True) -> Dict[str, Any]:
    """
    Enrich existing metadata with git information.

    Args:
        metadata: Existing metadata dict (or None to create new)
        path: Path to check for git context
        auto_detect: Automatically detect and add git metadata

    Returns:
        Metadata dict enriched with git information (if available)
    """
    result_metadata = metadata.copy() if metadata else {}

    if not auto_detect:
        return result_metadata

    # Only add git metadata if not already present
    git_data = get_git_metadata(path)

    if "branch" in git_data and "branch" not in result_metadata:
        result_metadata["branch"] = git_data["branch"]

    if "commit_hash" in git_data and "commit_hash" not in result_metadata:
        result_metadata["commit_hash"] = git_data["commit_hash"]

    logger.debug(f"Enriched metadata with git context: {git_data}")
    return result_metadata
