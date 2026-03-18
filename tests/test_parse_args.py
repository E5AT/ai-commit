"""Tests for argument parsing."""
import pytest
import sys
from unittest.mock import patch

import main


class TestParseArgs:
    """Tests for parse_args function."""

    def test_default_args(self, monkeypatch):
        """Test default argument values."""
        monkeypatch.setattr(sys, "argv", ["ai-commit"])
        args = main.parse_args()
        assert args.apply is False
        assert args.dry_run is True
        assert args.dir is None

    def test_apply_flag(self, monkeypatch):
        """Test --apply flag."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--apply"])
        args = main.parse_args()
        assert args.apply is True

    def test_dry_run_flag_explicit(self, monkeypatch):
        """Test --dry-run flag explicitly."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--dry-run"])
        args = main.parse_args()
        assert args.dry_run is True

    def test_dir_flag(self, monkeypatch):
        """Test --dir flag."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--dir", "/some/path"])
        args = main.parse_args()
        assert args.dir == "/some/path"

    def test_dir_flag_with_apply(self, monkeypatch):
        """Test --dir combined with --apply."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--dir", "/some/path", "--apply"])
        args = main.parse_args()
        assert args.dir == "/some/path"
        assert args.apply is True

    def test_all_flags_together(self, monkeypatch):
        """Test all flags together."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--apply", "--dry-run", "--dir", "/test"])
        args = main.parse_args()
        assert args.apply is True
        assert args.dry_run is True
        assert args.dir == "/test"

    def test_invalid_flag(self, monkeypatch):
        """Test with invalid flag."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "--invalid-flag"])
        with pytest.raises(SystemExit):
            main.parse_args()

    def test_positional_args_not_allowed(self, monkeypatch):
        """Test that positional arguments raise error."""
        monkeypatch.setattr(sys, "argv", ["ai-commit", "some_message"])
        with pytest.raises(SystemExit):
            main.parse_args()