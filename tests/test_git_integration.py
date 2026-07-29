"""
Tests for project-gated git context capture.

The server reads git state from its own cwd. In http/pm2 mode (and any stdio
session started outside the project) that cwd is the Omnispindle checkout, so
an ungated read stamps Omnispindle's branch/commit onto every project's todo —
wrong metadata that reads as authoritative in the dashboard.

These cover the gate: git context is captured only when the repo we are reading
is actually the todo's project.
"""

import subprocess

import pytest

from src.Omnispindle.git_integration import (
    _norm,
    enrich_metadata_with_git,
    get_changed_files,
    get_git_metadata,
    git_root_matches_project,
)


def _make_repo(root, name):
    """Create a git repo at root/name with one commit, return its path."""
    repo = root / name
    repo.mkdir(parents=True)
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "test@example.com")
    run("git", "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed\n")
    run("git", "add", "seed.txt")
    run("git", "commit", "-qm", "seed")
    return repo


@pytest.fixture
def repo(tmp_path):
    return _make_repo(tmp_path, "titancall")


class TestNorm:
    def test_folds_case_and_punctuation(self):
        assert _norm("MadQTT") == _norm("madqtt")
        assert _norm("madness_interactive") == _norm("Madness-Interactive")

    def test_distinct_names_stay_distinct(self):
        assert _norm("titancall") != _norm("omnispindle")


class TestGitRootMatchesProject:
    def test_matches_when_repo_is_the_project(self, repo):
        assert git_root_matches_project("titancall", str(repo)) is True

    def test_matches_case_insensitively(self, tmp_path):
        repo = _make_repo(tmp_path, "MadQTT")
        assert git_root_matches_project("madqtt", str(repo)) is True

    def test_rejects_a_different_repo(self, repo):
        # the bug: server sits in its own checkout, todo belongs elsewhere
        assert git_root_matches_project("omnispindle", str(repo)) is False

    def test_rejects_when_project_unknown(self, repo):
        assert git_root_matches_project(None, str(repo)) is False

    def test_rejects_outside_a_repo(self, tmp_path):
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        assert git_root_matches_project("not-a-repo", str(plain)) is False


class TestGetGitMetadata:
    def test_captures_branch_and_commit_for_matching_project(self, repo):
        meta = get_git_metadata(str(repo), project="titancall")
        assert meta["commit_hash"]
        assert meta["branch"]

    def test_captures_nothing_for_a_different_project(self, repo):
        assert get_git_metadata(str(repo), project="omnispindle") == {}

    def test_captures_nothing_without_a_project(self, repo):
        assert get_git_metadata(str(repo)) == {}


class TestEnrichMetadataWithGit:
    def test_adds_context_for_matching_project(self, repo):
        out = enrich_metadata_with_git({"tags": ["x"]}, path=str(repo), project="titancall")
        assert out["tags"] == ["x"]
        assert "commit_hash" in out and "branch" in out

    def test_leaves_metadata_untouched_on_mismatch(self, repo):
        out = enrich_metadata_with_git({"tags": ["x"]}, path=str(repo), project="omnispindle")
        assert out == {"tags": ["x"]}

    def test_does_not_overwrite_caller_supplied_values(self, repo):
        out = enrich_metadata_with_git({"commit_hash": "deadbee"}, path=str(repo), project="titancall")
        assert out["commit_hash"] == "deadbee"


class TestGetChangedFiles:
    def test_lists_changes_for_matching_project(self, repo):
        (repo / "seed.txt").write_text("dirty\n")
        assert get_changed_files(str(repo), project="titancall") == ["seed.txt"]

    def test_returns_nothing_for_a_different_project(self, repo):
        (repo / "seed.txt").write_text("dirty\n")
        assert get_changed_files(str(repo), project="omnispindle") == []

    def test_returns_nothing_without_a_project(self, repo):
        (repo / "seed.txt").write_text("dirty\n")
        assert get_changed_files(str(repo)) == []
