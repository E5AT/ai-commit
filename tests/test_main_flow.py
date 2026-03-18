"""Tests for main function and integration."""
import sys
from unittest.mock import MagicMock, patch

import pytest

import main


class TestMainFunction:
    """Tests for main function."""

    def test_main_flow_success(self, tmp_path, monkeypatch, mock_git_diff):
        """Test successful main flow."""
        # Mock the API
        mock_response = MagicMock()
        mock_response.text = "feat: add hello world script"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        # Mock environment
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            with patch.object(main, "get_staged_diff", return_value=mock_git_diff):
                with patch.object(main, "apply_git_commit") as mock_commit:
                    # Run main
                    monkeypatch.setattr(sys, "argv", ["ai-commit"])
                    main.main()

                    # Verify API was called
                    mock_model.generate_content.assert_called()

    def test_main_with_apply_flag(self, tmp_path, monkeypatch, mock_git_diff):
        """Test main with --apply flag."""
        mock_response = MagicMock()
        mock_response.text = "feat: add test file"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            with patch.object(main, "get_staged_diff", return_value=mock_git_diff):
                with patch.object(main, "apply_git_commit") as mock_commit:
                    monkeypatch.setattr(sys, "argv", ["ai-commit", "--apply"])
                    main.main()

                    mock_commit.assert_called_once()

    def test_main_without_apply_flag(self, tmp_path, monkeypatch, mock_git_diff):
        """Test main without --apply flag should not commit."""
        mock_response = MagicMock()
        mock_response.text = "feat: add test file"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            with patch.object(main, "get_staged_diff", return_value=mock_git_diff):
                with patch.object(main, "apply_git_commit") as mock_commit:
                    monkeypatch.setattr(sys, "argv", ["ai-commit"])
                    main.main()

                    mock_commit.assert_not_called()

    def test_main_no_staged_changes(self, tmp_path, monkeypatch):
        """Test main with no staged changes."""
        # Mock get_staged_diff to return empty diff
        monkeypatch.setattr(sys, "argv", ["ai-commit"])
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

        with patch.object(main, "get_staged_diff", return_value=""):
            with pytest.raises(SystemExit) as exc_info:
                main.main()
            assert exc_info.value.code == 0  # exits gracefully

    def test_main_missing_api_key(self, tmp_path, monkeypatch):
        """Test main with missing API key."""
        # Also mock load_dotenv to prevent reading from .env file
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(sys, "argv", ["ai-commit"])

        with patch.object(main, "load_dotenv"):
            # Mock get_staged_diff to return a diff so we get to the API key check
            with patch.object(main, "get_staged_diff", return_value="diff content"):
                with pytest.raises(SystemExit) as exc_info:
                    main.main()
                assert exc_info.value.code == 1

    def test_main_uses_correct_directory(self, tmp_path, monkeypatch, mock_git_diff):
        """Test that --dir flag is passed correctly."""
        mock_response = MagicMock()
        mock_response.text = "feat: test"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            with patch.object(main, "get_staged_diff") as mock_get_diff:
                mock_get_diff.return_value = mock_git_diff
                monkeypatch.setattr(sys, "argv", ["ai-commit", "--dir", str(tmp_path)])
                main.main()

                # Verify get_staged_diff was called with correct path
                mock_get_diff.assert_called_once_with(str(tmp_path))


class TestConstants:
    """Tests for constants and configuration."""

    def test_max_diff_length(self):
        """Test MAX_DIFF_LENGTH is set correctly."""
        assert main.MAX_DIFF_LENGTH == 4000

    def test_gemini_model_name(self):
        """Test GEMINI_MODEL is set correctly."""
        assert main.GEMINI_MODEL == "gemini-2.5-flash"

    def test_system_prompt_exists(self):
        """Test system prompt is defined."""
        assert len(main.SYSTEM_PROMPT) > 0
        assert "conventional commit" in main.SYSTEM_PROMPT.lower()