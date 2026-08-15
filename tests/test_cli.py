"""
Tests for sentry.cli module.

Tests CLI commands using Click's testing utilities.
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from sentry.cli import main


class TestCliStatus:
    """Test status command."""

    @patch("sentry.cli.HardwareReader")
    @patch("sentry.cli.Database")
    def test_status_command(self, mock_db: MagicMock, mock_reader: MagicMock) -> None:
        """Test status command output."""
        mock_metrics = MagicMock()
        mock_metrics.cpu_temp = 45.0
        mock_metrics.gpu_temp = 50.0
        mock_metrics.arm_voltage = 1.2
        mock_metrics.core_voltage = 1.2
        mock_metrics.throttled = 0
        mock_metrics.throttle_status = "normal"
        mock_metrics.timestamp = 1000000.0

        mock_reader.return_value.get_all_metrics.return_value = mock_metrics

        runner = CliRunner()
        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "CPU Temperature" in result.output
        assert "45.0" in result.output
        assert "GPU Temperature" in result.output

    @patch("sentry.cli.HardwareReader")
    def test_status_hardware_error(self, mock_reader: MagicMock) -> None:
        """Test status command with hardware error."""
        mock_reader.return_value.get_all_metrics.side_effect = OSError(
            "Hardware not available"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["status"])

        assert result.exit_code == 1
        assert "Error reading hardware metrics" in result.output


class TestCliMonitor:
    """Test monitor command."""

    @patch("sentry.cli.time.sleep")
    @patch("sentry.cli.HardwareReader")
    @patch("sentry.cli.Database")
    def test_monitor_command(
        self, mock_db: MagicMock, mock_reader: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Test monitor command starts."""
        mock_metrics = MagicMock()
        mock_metrics.cpu_temp = 45.0
        mock_metrics.gpu_temp = 50.0
        mock_metrics.arm_voltage = 1.2
        mock_metrics.core_voltage = 1.2
        mock_metrics.throttled = 0
        mock_metrics.throttle_status = "normal"
        mock_metrics.timestamp = 1000000.0

        mock_reader.return_value.get_all_metrics.return_value = mock_metrics
        # Make sleep raise KeyboardInterrupt to exit after one iteration
        mock_sleep.side_effect = KeyboardInterrupt

        runner = CliRunner()
        result = runner.invoke(main, ["monitor", "--interval", "1"])

        # Should have started and shown metrics before exit
        assert "Starting continuous monitoring" in result.output or "CPU Temperature" in result.output


class TestCliAlerts:
    """Test alerts command."""

    @patch("sentry.cli.Config.load")
    @patch("sentry.cli.AlertManager")
    def test_alerts_command_no_alerts(self, mock_mgr: MagicMock, mock_load: MagicMock) -> None:
        """Test alerts command with no alerts."""
        mock_mgr.return_value.get_recent_alerts.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ["alerts"])

        assert result.exit_code == 0
        assert "No alerts recorded" in result.output

    @patch("sentry.cli.Config.load")
    @patch("sentry.cli.AlertManager")
    def test_alerts_command_with_alerts(self, mock_mgr: MagicMock, mock_load: MagicMock) -> None:
        """Test alerts command with alerts."""
        mock_mgr.return_value.get_recent_alerts.return_value = [
            "HIGH_CPU_TEMP: CPU temperature 85.0°C"
        ]

        runner = CliRunner()
        result = runner.invoke(main, ["alerts"])

        assert result.exit_code == 0
        assert "HIGH_CPU_TEMP" in result.output

    @patch("sentry.cli.Config.load")
    @patch("sentry.cli.AlertManager")
    def test_alerts_clear(self, mock_mgr: MagicMock, mock_load: MagicMock) -> None:
        """Test alerts clear command."""
        runner = CliRunner()
        result = runner.invoke(main, ["alerts", "--clear"])

        assert result.exit_code == 0
        assert "Alerts log cleared" in result.output
        mock_mgr.return_value.clear_alerts.assert_called_once()


class TestCliConfig:
    """Test config command."""

    @patch("sentry.cli.Config")
    def test_config_show(self, mock_config: MagicMock) -> None:
        """Test config show command."""
        mock_cfg = MagicMock()
        mock_cfg.config_path = MagicMock()
        mock_cfg.config_path.__str__ = lambda self: "/test/config.toml"
        mock_cfg.cpu_temp_threshold = 70.0
        mock_cfg.gpu_temp_threshold = 70.0
        mock_cfg.arm_voltage_min = 1.2
        mock_cfg.core_voltage_min = 1.2
        mock_config.load.return_value = mock_cfg

        runner = CliRunner()
        result = runner.invoke(main, ["config", "--show"])

        assert result.exit_code == 0
        assert "CPU Temp Threshold" in result.output
        assert "70.0" in result.output

    @patch("sentry.cli.Config")
    def test_config_set_cpu_temp(self, mock_config: MagicMock) -> None:
        """Test setting CPU temperature threshold."""
        mock_cfg = MagicMock()
        mock_cfg.config_path = MagicMock()
        mock_cfg.config_path.__str__ = lambda self: "/test/config.toml"
        mock_cfg.validate.return_value = []
        mock_config.load.return_value = mock_cfg

        runner = CliRunner()
        result = runner.invoke(main, ["config", "--cpu-temp", "75.0"])

        assert result.exit_code == 0
        assert "Configuration saved" in result.output

    @patch("sentry.cli.Config")
    def test_config_reset(self, mock_config: MagicMock) -> None:
        """Test config reset command."""
        mock_cfg = MagicMock()
        mock_cfg.config_path = MagicMock()
        mock_cfg.config_path.exists.return_value = True
        mock_config.return_value.config_path = mock_cfg.config_path

        runner = CliRunner()
        result = runner.invoke(main, ["config", "--reset"])

        assert result.exit_code == 0
        assert "Configuration reset to defaults" in result.output

    @patch("sentry.cli.Config")
    def test_config_validation_error(self, mock_config: MagicMock) -> None:
        """Test config validation error."""
        mock_cfg = MagicMock()
        mock_cfg.validate.return_value = ["cpu_temp_threshold must be between 0 and 100"]
        mock_config.load.return_value = mock_cfg

        runner = CliRunner()
        result = runner.invoke(main, ["config", "--cpu-temp", "150.0"])

        assert result.exit_code == 1
        assert "Validation errors" in result.output


class TestCliVersion:
    """Test version command."""

    def test_version(self) -> None:
        """Test --version flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "version 0.1.0" in result.output


class TestCliHelp:
    """Test help command."""

    def test_help(self) -> None:
        """Test --help flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Sentry" in result.output
        assert "status" in result.output
        assert "monitor" in result.output
        assert "alert" in result.output
        assert "config" in result.output
