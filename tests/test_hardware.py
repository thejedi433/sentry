"""
Tests for sentry.hardware module.

Tests hardware metrics reading, parsing, and error handling.
Mocks vcgencmd and /sys filesystem reads.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentry.hardware import HardwareMetrics, HardwareReader


class TestHardwareMetrics:
    """Test HardwareMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Test creating HardwareMetrics instance."""
        metrics = HardwareMetrics(
            cpu_temp=45.0,
            gpu_temp=50.0,
            arm_voltage=1.2,
            core_voltage=1.2,
            throttled=0,
            throttle_status="normal",
            timestamp=time.time(),
        )
        assert metrics.cpu_temp == 45.0
        assert metrics.gpu_temp == 50.0
        assert metrics.arm_voltage == 1.2
        assert metrics.core_voltage == 1.2
        assert metrics.throttled == 0
        assert metrics.throttle_status == "normal"


class TestHardwareReaderInit:
    """Test HardwareReader initialization."""

    def test_default_paths(self) -> None:
        """Test default paths are set correctly."""
        reader = HardwareReader()
        assert reader.vcgencmd_path == "/opt/vc/bin/vcgencmd"
        assert reader.thermal_zone == Path("/sys/class/thermal/thermal_zone0/temp")

    def test_custom_paths(self) -> None:
        """Test custom paths can be set."""
        reader = HardwareReader(
            vcgencmd_path="/custom/vcgencmd",
            thermal_zone="/custom/thermal_zone/temp",
        )
        assert reader.vcgencmd_path == "/custom/vcgencmd"
        assert reader.thermal_zone == Path("/custom/thermal_zone/temp")


class TestParseVcgencmdTemp:
    """Test vcgencmd temperature parsing."""

    def test_parse_valid_temp(self) -> None:
        """Test parsing valid temperature output."""
        reader = HardwareReader()
        output = "temp=45.2'C"
        temp = reader._parse_vcgencmd_temp(output)
        assert temp == 45.2

    def test_parse_temp_with_decimal(self) -> None:
        """Test parsing temperature with decimals."""
        reader = HardwareReader()
        output = "temp=67.8'C"
        temp = reader._parse_vcgencmd_temp(output)
        assert temp == 67.8

    def test_parse_none_output(self) -> None:
        """Test parsing None returns None."""
        reader = HardwareReader()
        temp = reader._parse_vcgencmd_temp(None)
        assert temp is None

    def test_parse_empty_output(self) -> None:
        """Test parsing empty string returns None."""
        reader = HardwareReader()
        temp = reader._parse_vcgencmd_temp("")
        assert temp is None

    def test_parse_malformed_output(self) -> None:
        """Test parsing malformed output returns None."""
        reader = HardwareReader()
        temp = reader._parse_vcgencmd_temp("error reading temperature")
        assert temp is None


class TestParseVcgencmdVoltage:
    """Test vcgencmd voltage parsing."""

    def test_parse_valid_voltage(self) -> None:
        """Test parsing valid voltage output."""
        reader = HardwareReader()
        output = "volt=1.2000V"
        voltage = reader._parse_vcgencmd_voltage(output)
        assert voltage == 1.2

    def test_parse_voltage_with_decimal(self) -> None:
        """Test parsing voltage with decimals."""
        reader = HardwareReader()
        output = "volt=1.1500V"
        voltage = reader._parse_vcgencmd_voltage(output)
        assert voltage == 1.15

    def test_parse_none_voltage(self) -> None:
        """Test parsing None returns None."""
        reader = HardwareReader()
        voltage = reader._parse_vcgencmd_voltage(None)
        assert voltage is None

    def test_parse_empty_voltage(self) -> None:
        """Test parsing empty string returns None."""
        reader = HardwareReader()
        voltage = reader._parse_vcgencmd_voltage("")
        assert voltage is None


class TestParseThrottled:
    """Test throttling status parsing."""

    def test_parse_normal_status(self) -> None:
        """Test parsing normal (0x0) status."""
        reader = HardwareReader()
        output = "throttled=0x0"
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 0
        assert status == "normal"

    def test_parse_under_voltage(self) -> None:
        """Test parsing under-voltage flag."""
        reader = HardwareReader()
        output = "throttled=0x1"
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 1
        assert "under-voltage" in status

    def test_parse_freq_capped(self) -> None:
        """Test parsing frequency capped flag."""
        reader = HardwareReader()
        output = "throttled=0x2"
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 2
        assert "freq-capped" in status

    def test_parse_throttled_flag(self) -> None:
        """Test parsing throttled flag."""
        reader = HardwareReader()
        output = "throttled=0x4"
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 4
        assert "throttled" in status

    def test_parse_multiple_flags(self) -> None:
        """Test parsing multiple flags."""
        reader = HardwareReader()
        output = "throttled=0x7"  # Bits 0, 1, 2
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 7
        assert "under-voltage" in status
        assert "freq-capped" in status
        assert "throttled" in status

    def test_parse_occurred_flags(self) -> None:
        """Test parsing occurred flags (bits 16+)."""
        reader = HardwareReader()
        output = "throttled=0x50000"  # Bits 16 and 18
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 0x50000
        assert "uv-occurred" in status
        assert "throttling-occurred" in status

    def test_parse_none_throttled(self) -> None:
        """Test parsing None returns (0, unknown)."""
        reader = HardwareReader()
        bitmask, status = reader._parse_throttled(None)
        assert bitmask == 0
        assert status == "unknown"

    def test_parse_malformed_throttled(self) -> None:
        """Test parsing malformed output returns (0, unknown)."""
        reader = HardwareReader()
        output = "error reading throttled"
        bitmask, status = reader._parse_throttled(output)
        assert bitmask == 0
        assert status == "unknown"


class TestRunVcgencmd:
    """Test vcgencmd execution."""

    @patch("os.path.exists")
    @patch("subprocess.run")
    def test_vcgencmd_success(self, mock_run: MagicMock, mock_exists: MagicMock) -> None:
        """Test successful vcgencmd execution."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0, stdout="temp=45.0'C", stderr=""
        )

        reader = HardwareReader()
        output = reader._run_vcgencmd("measure_temp")

        assert output == "temp=45.0'C"
        mock_run.assert_called_once()

    @patch("os.path.exists")
    def test_vcgencmd_not_found(self, mock_exists: MagicMock) -> None:
        """Test when vcgencmd doesn't exist."""
        mock_exists.return_value = False

        reader = HardwareReader()
        output = reader._run_vcgencmd("measure_temp")

        assert output is None

    @patch("os.path.exists")
    @patch("subprocess.run")
    def test_vcgencmd_timeout(self, mock_run: MagicMock, mock_exists: MagicMock) -> None:
        """Test vcgencmd timeout handling."""
        import subprocess

        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired("vcgencmd", 5)

        reader = HardwareReader()
        output = reader._run_vcgencmd("measure_temp")

        assert output is None

    @patch("os.path.exists")
    @patch("subprocess.run")
    def test_vcgencmd_permission_error(
        self, mock_run: MagicMock, mock_exists: MagicMock
    ) -> None:
        """Test vcgencmd permission error handling."""
        mock_exists.return_value = True
        mock_run.side_effect = PermissionError("Permission denied")

        reader = HardwareReader()
        output = reader._run_vcgencmd("measure_temp")

        assert output is None


class TestReadThermalZone:
    """Test thermal zone reading."""

    def test_read_valid_temp(self, tmp_path: Path) -> None:
        """Test reading valid thermal zone."""
        thermal_file = tmp_path / "thermal_zone"
        thermal_file.write_text("45000")  # 45.0°C in millidegrees

        reader = HardwareReader(thermal_zone=str(thermal_file))
        temp = reader._read_thermal_zone()

        assert temp == 45.0

    def test_read_decimal_temp(self, tmp_path: Path) -> None:
        """Test reading temperature with decimal."""
        thermal_file = tmp_path / "thermal_zone"
        thermal_file.write_text("67500")  # 67.5°C

        reader = HardwareReader(thermal_zone=str(thermal_file))
        temp = reader._read_thermal_zone()

        assert temp == 67.5

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """Test reading nonexistent thermal zone."""
        reader = HardwareReader(thermal_zone=str(tmp_path / "nonexistent"))
        temp = reader._read_thermal_zone()

        assert temp is None

    def test_read_invalid_content(self, tmp_path: Path) -> None:
        """Test reading invalid thermal zone content."""
        thermal_file = tmp_path / "thermal_zone"
        thermal_file.write_text("invalid")

        reader = HardwareReader(thermal_zone=str(thermal_file))
        temp = reader._read_thermal_zone()

        assert temp is None


class TestGetAllMetrics:
    """Test getting all metrics."""

    @patch.object(HardwareReader, "get_cpu_temp")
    @patch.object(HardwareReader, "get_gpu_temp")
    @patch.object(HardwareReader, "get_arm_voltage")
    @patch.object(HardwareReader, "get_core_voltage")
    @patch.object(HardwareReader, "get_throttled")
    def test_get_all_metrics(
        self,
        mock_throttled: MagicMock,
        mock_core: MagicMock,
        mock_arm: MagicMock,
        mock_gpu: MagicMock,
        mock_cpu: MagicMock,
    ) -> None:
        """Test getting all metrics."""
        mock_cpu.return_value = 45.0
        mock_gpu.return_value = 50.0
        mock_arm.return_value = 1.2
        mock_core.return_value = 1.2
        mock_throttled.return_value = (0, "normal")

        reader = HardwareReader()
        metrics = reader.get_all_metrics()

        assert metrics.cpu_temp == 45.0
        assert metrics.gpu_temp == 50.0
        assert metrics.arm_voltage == 1.2
        assert metrics.core_voltage == 1.2
        assert metrics.throttled == 0
        assert metrics.throttle_status == "normal"
        assert isinstance(metrics.timestamp, float)

    @patch.object(HardwareReader, "get_cpu_temp")
    @patch.object(HardwareReader, "get_gpu_temp")
    @patch.object(HardwareReader, "get_arm_voltage")
    @patch.object(HardwareReader, "get_core_voltage")
    @patch.object(HardwareReader, "get_throttled")
    def test_get_all_metrics_unavailable(
        self,
        mock_throttled: MagicMock,
        mock_core: MagicMock,
        mock_arm: MagicMock,
        mock_gpu: MagicMock,
        mock_cpu: MagicMock,
    ) -> None:
        """Test getting all metrics when some unavailable."""
        mock_cpu.return_value = None
        mock_gpu.return_value = None
        mock_arm.return_value = None
        mock_core.return_value = None
        mock_throttled.return_value = (0, "unknown")

        reader = HardwareReader()
        metrics = reader.get_all_metrics()

        # Should default to 0.0 when unavailable
        assert metrics.cpu_temp == 0.0
        assert metrics.gpu_temp == 0.0
        assert metrics.arm_voltage == 0.0
        assert metrics.core_voltage == 0.0
