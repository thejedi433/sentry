"""
Tests for sentry history and stats commands.

Tests the history and stats CLI commands and their integration with the database.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from sentry.cli import main
from sentry.hardware import HardwareMetrics


class TestHistoryCommand:
    """Test history command."""

    @patch("sentry.cli.Database")
    def test_history_empty_db(self, mock_db: MagicMock) -> None:
        """Test history command with empty database."""
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_recent_readings.return_value = []
        
        runner = CliRunner()
        result = runner.invoke(main, ["history"])
        
        assert result.exit_code == 0
        assert "No historical readings found" in result.output

    @patch("sentry.cli.Database")
    def test_history_with_readings(self, mock_db: MagicMock) -> None:
        """Test history command with readings."""
        metrics = HardwareMetrics(
            cpu_temp=45.0,
            gpu_temp=50.0,
            arm_voltage=1.2,
            core_voltage=1.2,
            throttled=0,
            throttle_status="normal",
            timestamp=time.time(),
        )
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_recent_readings.return_value = [metrics]

        runner = CliRunner()
        result = runner.invoke(main, ["history"])

        assert result.exit_code == 0
        assert "Historical Readings" in result.output
        assert "CPU: 45.0°C" in result.output
        assert "GPU: 50.0°C" in result.output
        assert "ARM: 1.20V" in result.output

    @patch("sentry.cli.Database")
    def test_history_with_limit(self, mock_db: MagicMock) -> None:
        """Test history command with limit parameter."""
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_recent_readings.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ["history", "--limit", "5"])

        assert result.exit_code == 0
        # Verify get_recent_readings was called with limit=5
        mock_instance.get_recent_readings.assert_called_once_with(
            limit=5, minutes=None
        )

    @patch("sentry.cli.Database")
    def test_history_with_minutes(self, mock_db: MagicMock) -> None:
        """Test history command with minutes parameter."""
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_recent_readings.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ["history", "--minutes", "30"])

        assert result.exit_code == 0
        # Verify get_recent_readings was called with minutes=30
        mock_instance.get_recent_readings.assert_called_once_with(
            limit=10, minutes=30
        )


class TestStatsCommand:
    """Test stats command."""

    @patch("sentry.cli.Database")
    def test_stats_empty_db(self, mock_db: MagicMock) -> None:
        """Test stats command with empty database."""
        mock_stats = {
            "cpu_temp": {"min": None, "max": None, "avg": None},
            "gpu_temp": {"min": None, "max": None, "avg": None},
            "arm_voltage": {"min": None, "max": None, "avg": None},
            "core_voltage": {"min": None, "max": None, "avg": None},
        }
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_stats.return_value = mock_stats
        mock_instance.count_readings.return_value = 0

        runner = CliRunner()
        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Statistics" in result.output
        assert "No data available" in result.output
        assert "Total readings in database: 0" in result.output

    @patch("sentry.cli.Database")
    def test_stats_with_data(self, mock_db: MagicMock) -> None:
        """Test stats command with data."""
        mock_stats = {
            "cpu_temp": {"min": 40.0, "max": 50.0, "avg": 45.0},
            "gpu_temp": {"min": 45.0, "max": 55.0, "avg": 50.0},
            "arm_voltage": {"min": 1.15, "max": 1.25, "avg": 1.2},
            "core_voltage": {"min": 1.18, "max": 1.22, "avg": 1.2},
        }
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_stats.return_value = mock_stats
        mock_instance.count_readings.return_value = 10

        runner = CliRunner()
        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Statistics" in result.output
        assert "cpu_temp:" in result.output
        assert "Min: 40.0°C" in result.output
        assert "Max: 50.0°C" in result.output
        assert "Avg: 45.0°C" in result.output
        assert "arm_voltage:" in result.output
        assert "Min: 1.15V" in result.output
        assert "Total readings in database: 10" in result.output

    @patch("sentry.cli.Database")
    def test_stats_with_minutes(self, mock_db: MagicMock) -> None:
        """Test stats command with minutes parameter."""
        mock_stats = {
            "cpu_temp": {"min": 40.0, "max": 50.0, "avg": 45.0},
            "gpu_temp": {"min": 45.0, "max": 55.0, "avg": 50.0},
            "arm_voltage": {"min": 1.15, "max": 1.25, "avg": 1.2},
            "core_voltage": {"min": 1.18, "max": 1.22, "avg": 1.2},
        }
        mock_instance = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_instance
        mock_instance.get_stats.return_value = mock_stats
        mock_instance.count_readings.return_value = 5

        runner = CliRunner()
        result = runner.invoke(main, ["stats", "--minutes", "1440"])

        assert result.exit_code == 0
        # Verify get_stats was called with minutes=1440
        mock_instance.get_stats.assert_called_once_with(minutes=1440)
        assert "last 1440 minutes" in result.output
