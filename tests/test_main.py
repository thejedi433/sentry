"""Tests for __main__ module."""

import subprocess
import sys


def test_python_m_invocation():
    """Test that python -m sentry works."""
    result = subprocess.run(
        [sys.executable, "-m", "sentry", "--version"],
        capture_output=True,
        text=True,
        cwd="src",
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_python_m_help():
    """Test that python -m sentry --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "sentry", "--help"],
        capture_output=True,
        text=True,
        cwd="src",
    )
    assert result.returncode == 0
    assert "sentry" in result.stdout.lower() or "usage" in result.stdout.lower()
