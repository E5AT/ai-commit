"""Tests for edge cases and error handling."""
import sys
from unittest.mock import MagicMock, patch

import pytest

import main


class TestEdgeCases:
    """Edge case tests."""

    def test_very_long_diff(self, monkeypatch):
        """Test with very large diff that gets truncated."""
        # Create a diff longer than MAX_DIFF_LENGTH
        long_diff = "diff --git a/test.py b/test.py\n" + "a" * 10000

        result = main.truncate_diff(long_diff)
        # The result should include truncation message
        assert "[diff truncated" in result
        # And should be approximately MAX_DIFF_LENGTH + truncation message length
        assert len(result) <= main.MAX_DIFF_LENGTH + 50  # extra for truncation message

    def test_diff_exactly_at_limit(self):
        """Test diff exactly at the max length."""
        # Create diff exactly at MAX_DIFF_LENGTH
        diff = "a" * main.MAX_DIFF_LENGTH
        result = main.truncate_diff(diff)
        assert result == diff  # Should not be truncated

    def test_diff_just_over_limit(self):
        """Test diff just over the max length."""
        diff = "a" * (main.MAX_DIFF_LENGTH + 1)
        result = main.truncate_diff(diff)
        assert "[diff truncated" in result
        assert len(result) <= main.MAX_DIFF_LENGTH + 30

    def test_empty_string_diff(self):
        """Test with empty string."""
        result = main.truncate_diff("")
        assert result == ""

    def test_unicode_diff(self):
        """Test with unicode characters in diff."""
        unicode_diff = "diff --git a/test.py b/test.py\n+++ b/test.py\n@@ -1,1 +1,2 @@\n+print('Hello 🌍')\n+print('こんにちは')"
        result = main.truncate_diff(unicode_diff)
        assert "🌍" in result
        assert "こんにちは" in result

    def test_special_characters_in_diff(self):
        """Test with special characters in diff."""
        special_diff = 'diff --git a/test.py b/test.py\n+++ b/test.py\n@@ -1,1 +1,2 @@\n+print("Hello \\n\\t\\"")\n+print("Path: C:\\\\Users\\\\test")'
        result = main.truncate_diff(special_diff)
        assert "\\\\" in result or "\\n" in result

    def test_binary_file_diff(self):
        """Test with binary file diff (should still work)."""
        binary_diff = "diff --git a/binary.png b/binary.png\nnew file mode 100644\nBinary files /dev/null and b/binary.png differ"
        result = main.truncate_diff(binary_diff)
        assert "Binary files" in result


class TestErrorHandling:
    """Tests for error handling."""

    def test_get_staged_diff_handles_error_messages(self, tmp_path):
        """Test that error messages from git are handled."""
        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git diff --staged")
            with pytest.raises(SystemExit) as exc_info:
                main.get_staged_diff(str(tmp_path))
            assert exc_info.value.code == 1

    def test_call_gemini_preserves_error_details(self, mock_env_api_key):
        """Test that API errors preserve details."""
        import google.generativeai as genai

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = ValueError("Invalid request")

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            with pytest.raises(SystemExit) as exc_info:
                main.call_gemini_api("test diff", "test_key")
            assert exc_info.value.code == 1


class TestCLIBehavior:
    """Tests for CLI behavior edge cases."""

    def test_argparse_unknown_argument(self, monkeypatch):
        """Test unknown argument handling."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--unknown-argument"])
        with pytest.raises(SystemExit):
            main.parse_args()

    def test_argparse_missing_value(self, monkeypatch):
        """Test missing argument value."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--dir"])
        with pytest.raises(SystemExit):
            main.parse_args()


class TestRetryLogic:
    """Tests for retry logic in API calls."""

    def test_retry_on_first_failure(self, mock_env_api_key):
        """Test that retry happens on first API failure."""
        import google.generativeai as genai

        call_count = 0

        def side_effect(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            return MagicMock(text="feat: success after retry")

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = side_effect

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            result = main.call_gemini_api("test diff", "test_key")
            assert result == "feat: success after retry"
            assert call_count == 2

    def test_both_retries_fail(self, mock_env_api_key):
        """Test when both API attempts fail."""
        import google.generativeai as genai

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("Persistent error")

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            with pytest.raises(SystemExit) as exc_info:
                main.call_gemini_api("test diff", "test_key")
            assert exc_info.value.code == 1