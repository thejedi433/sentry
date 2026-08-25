"""Tests to achieve 100% coverage for sentry."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from sentry.alerts import AlertManager
from sentry.config import Config
from sentry.hardware import HardwareMetrics


class TestAlertManagerEdgeCases:
    """Test edge cases in AlertManager to cover remaining lines."""

    def test_get_recent_alerts_after_removing_file(self, tmp_path):
        """Test get_recent_alerts when log file is removed after init."""
        log_path = tmp_path / "alerts.log"
        config = Config()
        manager = AlertManager(config, log_path)

        # File handler creates the file during init; remove it to hit line 129
        if log_path.exists():
            log_path.unlink()

        alerts = manager.get_recent_alerts()
        assert alerts == []

    def test_get_recent_alerts_read_error(self, tmp_path):
        """Test get_recent_alerts when file read fails (lines 137-138)."""
        log_path = tmp_path / "alerts.log"
        config = Config()
        manager = AlertManager(config, log_path)

        # Write some content first
        log_path.write_text("2026-08-25 12:00:00 - WARNING - test alert")

        # Mock read_text to raise an exception -> hits the except block
        with patch.object(Path, 'read_text', side_effect=PermissionError("denied")):
            alerts = manager.get_recent_alerts()
            assert alerts == []


class TestCliMonitorOSErrorContinue:
    """Test CLI monitor OSError continue path (line 80)."""

    def test_monitor_oserror_continues_loop(self):
        """Test that monitor loop continues after OSError."""
        from click.testing import CliRunner
        from sentry.cli import main

        runner = CliRunner()

        call_count = 0

        def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt()

        with patch('sentry.cli.HardwareReader') as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader_class.return_value = mock_reader
            mock_reader.get_all_metrics.side_effect = OSError("no hw")

            with patch('time.sleep', side_effect=mock_sleep):
                result = runner.invoke(main, ['monitor', '--interval', '1'])
                assert "Error: Unable to read hardware metrics" in result.output


class TestCliHistoryStatsEdgeCases:
    """Test CLI history/stats edge cases."""

    def test_history_no_readings_message(self):
        """Test history command output when no readings found."""
        from click.testing import CliRunner
        from sentry.cli import main

        runner = CliRunner()

        with patch('sentry.cli.Database') as mock_db_class:
            mock_db = MagicMock()
            mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_db_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.get_recent_readings.return_value = []

            result = runner.invoke(main, ['history'])
            assert "No historical readings found." in result.output

    def test_stats_with_none_min(self):
        """Test stats command when min values are None (no data)."""
        from click.testing import CliRunner
        from sentry.cli import main

        runner = CliRunner()

        no_data_stats = {
            "cpu_temp": {"min": None, "max": None, "avg": None},
            "gpu_temp": {"min": None, "max": None, "avg": None},
            "arm_voltage": {"min": None, "max": None, "avg": None},
            "core_voltage": {"min": None, "max": None, "avg": None},
        }

        with patch('sentry.cli.Database') as mock_db_class:
            mock_db = MagicMock()
            mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_db_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.get_stats.return_value = no_data_stats
            mock_db.count_readings.return_value = 0

            result = runner.invoke(main, ['stats'])
            assert "No data available" in result.output
