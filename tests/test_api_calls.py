"""Tests for API operations."""
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

import main


class TestGetGeminiApiKey:
    """Tests for get_gemini_api_key function."""

    def test_get_api_key_success(self, mock_env_api_key, monkeypatch):
        """Test successful API key retrieval."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test_key_12345")
        result = main.get_gemini_api_key()
        assert result == "test_key_12345"

    def test_get_api_key_missing(self, monkeypatch):
        """Test missing API key."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            main.get_gemini_api_key()
        assert exc_info.value.code == 1


class TestCallGeminiApi:
    """Tests for call_gemini_api function."""

    def test_call_gemini_api_success(self, mock_git_diff, mock_env_api_key):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.text = "feat: add new feature"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            result = main.call_gemini_api(mock_git_diff, "test_key")
            assert result == "feat: add new feature"

    def test_call_gemini_api_empty_response(self, mock_git_diff, mock_env_api_key):
        """Test when API returns empty response."""
        mock_response = MagicMock()
        mock_response.text = None

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            with pytest.raises(SystemExit) as exc_info:
                main.call_gemini_api(mock_git_diff, "test_key")
            assert exc_info.value.code == 1

    def test_call_gemini_api_whitespace_response(self, mock_git_diff, mock_env_api_key):
        """Test when API returns only whitespace."""
        mock_response = MagicMock()
        mock_response.text = "   \n\t  "

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch.object(main.genai, "GenerativeModel", return_value=mock_model):
            result = main.call_gemini_api(mock_git_diff, "test_key")
            # Should be stripped
            assert result == ""

    def test_call_gemini_api_network_error(self, mock_git_diff, mock_env_api_key):
        """Test network error handling."""
        import google.generativeai as genai

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("Network error")

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            # First attempt fails, retry also fails
            with pytest.raises(SystemExit) as exc_info:
                main.call_gemini_api(mock_git_diff, "test_key")
            assert exc_info.value.code == 1

    def test_call_gemini_api_invalid_key(self, mock_git_diff, monkeypatch):
        """Test with invalid API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "invalid_key")
        import google.generativeai as genai

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API key not valid")

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            with pytest.raises(SystemExit) as exc_info:
                main.call_gemini_api(mock_git_diff, "invalid_key")
            assert exc_info.value.code == 1

    def test_call_gemini_api_retry_on_error(self, mock_git_diff, mock_env_api_key):
        """Test that API is called twice on error (retry logic)."""
        import google.generativeai as genai

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call failed")
            return MagicMock(text="feat: retry success")

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = side_effect

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            result = main.call_gemini_api(mock_git_diff, "test_key")
            assert call_count == 2
            assert result == "feat: retry success"

    def test_call_gemini_api_exception_message_preserved(self, mock_git_diff, mock_env_api_key):
        """Test that exception message is preserved in error output."""
        import google.generativeai as genai
        import io
        from contextlib import redirect_stderr

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("Specific error message")

        with patch.object(genai, "GenerativeModel", return_value=mock_model):
            with pytest.raises(SystemExit) as exc_info:
                main.call_gemini_api(mock_git_diff, "test_key")
            assert exc_info.value.code == 1