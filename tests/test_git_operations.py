"""Tests for git operations."""
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import main


class TestGetStagedDiff:
    """Tests for get_staged_diff function."""

    def test_get_staged_diff_success(self, tmp_path, monkeypatch):
        """Test successful retrieval of staged diff."""
        # Use mocking instead of actual git commands
        mock_diff_output = """diff --git a/test.py b/test.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/test.py
@@ -0,0 +1 @@
+print('hello')
"""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_diff_output
            mock_run.return_value = mock_result

            diff = main.get_staged_diff(str(tmp_path))
            assert "print('hello')" in diff

    def test_get_staged_diff_no_repo(self):
        """Test when not in a git repository."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            with pytest.raises(SystemExit) as exc_info:
                main.get_staged_diff("/nonexistent")
            assert exc_info.value.code == 1

    def test_get_staged_diff_git_not_installed(self):
        """Test when git is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError("git")):
            with pytest.raises(SystemExit) as exc_info:
                main.get_staged_diff()
            assert exc_info.value.code == 1


class TestCheckStagedChanges:
    """Tests for check_staged_changes function."""

    def test_check_staged_changes_with_diff(self, mock_git_diff):
        """Test with valid staged changes."""
        result = main.check_staged_changes(mock_git_diff)
        assert result is True

    def test_check_staged_changes_empty_diff(self, empty_diff, capsys):
        """Test with empty diff - should exit gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            main.check_staged_changes(empty_diff)
        assert exc_info.value.code == 0  # exits gracefully with code 0
        captured = capsys.readouterr()
        assert "No staged changes found" in captured.out

    def test_check_staged_changes_whitespace_only(self, capsys):
        """Test with whitespace-only diff."""
        with pytest.raises(SystemExit) as exc_info:
            main.check_staged_changes("   \n\t  ")
        assert exc_info.value.code == 0


class TestTruncateDiff:
    """Tests for truncate_diff function."""

    def test_truncate_diff_short(self, mock_git_diff):
        """Test that short diffs are not truncated."""
        result = main.truncate_diff(mock_git_diff)
        assert result == mock_git_diff
        assert "[diff truncated" not in result

    def test_truncate_diff_long(self, large_diff):
        """Test that large diffs are truncated."""
        result = main.truncate_diff(large_diff)
        assert len(result) == main.MAX_DIFF_LENGTH + len("\n\n[diff truncated for brevity]")
        assert "[diff truncated" in result
        assert result.endswith("for brevity]")

    def test_truncate_diff_at_boundary(self):
        """Test diff exactly at max length."""
        diff = "a" * main.MAX_DIFF_LENGTH
        result = main.truncate_diff(diff)
        # At exactly MAX_DIFF_LENGTH, no truncation needed
        assert result == diff


class TestApplyGitCommit:
    """Tests for apply_git_commit function."""

    def test_apply_git_commit_success(self, tmp_path, monkeypatch):
        """Test successful git commit."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        # Create and stage a file
        (tmp_path / "test.txt").write_text("test content")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_path, capture_output=True)

        # Now apply commit
        result = main.apply_git_commit("test: initial commit", str(tmp_path))
        # Check the commit was created
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )
        assert "test: initial commit" in log.stdout

    def test_apply_git_commit_failure(self, tmp_path):
        """Test git commit failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git commit")
            with pytest.raises(SystemExit) as exc_info:
                main.apply_git_commit("test: message", str(tmp_path))
            assert exc_info.value.code == 1