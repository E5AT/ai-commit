"""Shared fixtures for ai-commit tests."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_git_diff():
    """Sample git diff for testing."""
    return """diff --git a/main.py b/main.py
index 1234567..89abcdef 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,5 @@
+import new_module
+
 def hello():
     print("Hello, World!")
+    print("New line added")
"""


@pytest.fixture
def large_diff():
    """A very large diff to test truncation."""
    return "a" * 10000


@pytest.fixture
def empty_diff():
    """Empty diff string."""
    return ""


@pytest.fixture
def mock_genai_module():
    """Mock the google.generativeai module."""
    with patch.dict(sys.modules, {'google': MagicMock(), 'google.generativeai': MagicMock()}):
        yield


@pytest.fixture
def mock_env_api_key(monkeypatch):
    """Set mock API key in environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key_12345")


@pytest.fixture
def mock_gemini_response():
    """Create a mock Gemini API response."""
    mock_response = MagicMock()
    mock_response.text = "feat: add new feature"
    return mock_response


@pytest.fixture
def mock_gemini_model():
    """Create a mock Gemini model."""
    mock_model = MagicMock()
    mock_model.generate_content.return_value = MagicMock(text="feat: add new feature")
    return mock_model


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    # Initialize git repo
    subprocess = pytest.importorskip("subprocess")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, capture_output=True)

    return tmp_path