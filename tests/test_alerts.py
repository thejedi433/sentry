"""
Tests for sentry.alerts module.

Tests alert checking, logging, and retrieval.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sentry.alerts import AlertManager
from sentry.config import Config
from sentry.hardware import HardwareMetrics


@pytest.fixture
def temp_log() -> Path:
    """Create a temporary log file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "alerts.log"
        yield log_path


@pytest.fixture
def sample_metrics() -> HardwareMetrics:
    """Create sample hardware metrics."""
    return HardwareMetrics(
        cpu_temp=45.0,
        gpu_temp=50.0,
        arm_voltage=1.2,
        core_voltage=1.2,
        throttled=0,
        throttle_status="normal",
        timestamp=1000000.0,
    )


@pytest.fixture
def high_temp_metrics() -> HardwareMetrics:
    """Create metrics with high CPU temperature."""
    return HardwareMetrics(
        cpu_temp=85.0,
        gpu_temp=50.0,
        arm_voltage=1.2,
        core_voltage=1.2,
        throttled=0,
        throttle_status="normal",
        timestamp=1000000.0,
    )


@pytest.fixture
def low_voltage_metrics() -> HardwareMetrics:
    """Create metrics with low voltage."""
    return HardwareMetrics(
        cpu_temp=45.0,
        gpu_temp=50.0,
        arm_voltage=1.0,
        core_voltage=1.0,
        throttled=0,
        throttle_status="normal",
        timestamp=1000000.0,
    )


@pytest.fixture
def throttled_metrics() -> HardwareMetrics:
    """Create metrics with throttling."""
    return HardwareMetrics(
        cpu_temp=45.0,
        gpu_temp=50.0,
        arm_voltage=1.2,
        core_voltage=1.2,
        throttled=0x7,
        throttle_status="under-voltage, freq-capped, throttled",
        timestamp=1000000.0,
    )


class TestAlertManagerInit:
    """Test AlertManager initialization."""

    def test_init_default_config(self, temp_log: Path) -> None:
        """Test initialization with default config."""
        mgr = AlertManager(log_path=temp_log)
        assert mgr.config is not None
        assert mgr.log_path == temp_log

    def test_init_custom_config(self, temp_log: Path) -> None:
        """Test initialization with custom config."""
        config = Config(cpu_temp_threshold=80.0)
        mgr = AlertManager(config=config, log_path=temp_log)
        assert mgr.config.cpu_temp_threshold == 80.0


class TestCheckThresholds:
    """Test threshold checking."""

    def test_no_alerts_normal_metrics(
        self, temp_log: Path, sample_metrics: HardwareMetrics
    ) -> None:
        """Test no alerts for normal metrics."""
        mgr = AlertManager(log_path=temp_log)
        alerts = mgr.check_thresholds(sample_metrics)
        assert alerts == []

    def test_cpu_temp_alert(
        self, temp_log: Path, high_temp_metrics: HardwareMetrics
    ) -> None:
        """Test CPU temperature alert."""
        mgr = AlertManager(log_path=temp_log)
        alerts = mgr.check_thresholds(high_temp_metrics)

        assert len(alerts) == 1
        assert "HIGH_CPU_TEMP" in alerts[0]
        assert "85.0" in alerts[0]

    def test_gpu_temp_alert(self, temp_log: Path) -> None:
        """Test GPU temperature alert."""
        mgr = AlertManager(log_path=temp_log)
        metrics = HardwareMetrics(
            cpu_temp=45.0,
            gpu_temp=80.0,
            arm_voltage=1.2,
            core_voltage=1.2,
            throttled=0,
            throttle_status="normal",
            timestamp=1000000.0,
        )
        alerts = mgr.check_thresholds(metrics)

        assert len(alerts) == 1
        assert "HIGH_GPU_TEMP" in alerts[0]

    def test_low_arm_voltage_alert(
        self, temp_log: Path, low_voltage_metrics: HardwareMetrics
    ) -> None:
        """Test low ARM voltage alert."""
        mgr = AlertManager(log_path=temp_log)
        alerts = mgr.check_thresholds(low_voltage_metrics)

        # Should have 2 alerts: low ARM and low core voltage
        arm_alerts = [a for a in alerts if "LOW_ARM_VOLTAGE" in a]
        assert len(arm_alerts) >= 1

    def test_throttle_alert(
        self, temp_log: Path, throttled_metrics: HardwareMetrics
    ) -> None:
        """Test throttling alert."""
        mgr = AlertManager(log_path=temp_log)
        alerts = mgr.check_thresholds(throttled_metrics)

        assert len(alerts) == 1
        assert "THROTTLED" in alerts[0]

    def test_multiple_alerts(self, temp_log: Path) -> None:
        """Test multiple simultaneous alerts."""
        mgr = AlertManager(log_path=temp_log)
        metrics = HardwareMetrics(
            cpu_temp=85.0,
            gpu_temp=80.0,
            arm_voltage=1.0,
            core_voltage=1.0,
            throttled=0x4,
            throttle_status="throttled",
            timestamp=1000000.0,
        )
        alerts = mgr.check_thresholds(metrics)

        assert len(alerts) >= 4  # CPU, GPU, ARM, Core, throttling

    def test_alert_logs_to_file(
        self, temp_log: Path, high_temp_metrics: HardwareMetrics
    ) -> None:
        """Test alerts are logged to file."""
        mgr = AlertManager(log_path=temp_log)
        mgr.check_thresholds(high_temp_metrics)

        assert temp_log.exists()
        content = temp_log.read_text()
        assert "HIGH_CPU_TEMP" in content


class TestGetRecentAlerts:
    """Test retrieving recent alerts."""

    def test_get_alerts_empty_log(self, temp_log: Path) -> None:
        """Test getting alerts from empty log."""
        mgr = AlertManager(log_path=temp_log)
        alerts = mgr.get_recent_alerts()
        assert alerts == []

    def test_get_alerts_nonexistent_log(self, temp_log: Path) -> None:
        """Test getting alerts when log doesn't exist."""
        mgr = AlertManager(log_path=temp_log)
        alerts = mgr.get_recent_alerts()
        assert alerts == []

    def test_get_alerts_limit(self, temp_log: Path) -> None:
        """Test alert limit is respected."""
        mgr = AlertManager(log_path=temp_log)

        # Create multiple alerts
        for i in range(30):
            metrics = HardwareMetrics(
                cpu_temp=85.0,
                gpu_temp=50.0,
                arm_voltage=1.2,
                core_voltage=1.2,
                throttled=0,
                throttle_status="normal",
                timestamp=1000000.0 + i,
            )
            mgr.check_thresholds(metrics)

        alerts = mgr.get_recent_alerts(limit=10)
        assert len(alerts) <= 10

    def test_get_alerts_ordering(self, temp_log: Path) -> None:
        """Test alerts are returned in order."""
        mgr = AlertManager(log_path=temp_log)

        metrics1 = HardwareMetrics(
            cpu_temp=85.0,
            gpu_temp=50.0,
            arm_voltage=1.2,
            core_voltage=1.2,
            throttled=0,
            throttle_status="normal",
            timestamp=1000000.0,
        )
        mgr.check_thresholds(metrics1)

        metrics2 = HardwareMetrics(
            cpu_temp=90.0,
            gpu_temp=50.0,
            arm_voltage=1.2,
            core_voltage=1.2,
            throttled=0,
            throttle_status="normal",
            timestamp=2000000.0,
        )
        mgr.check_thresholds(metrics2)

        alerts = mgr.get_recent_alerts(limit=5)
        # Most recent should be last
        assert "90.0" in alerts[-1]


class TestClearAlerts:
    """Test clearing alerts."""

    def test_clear_alerts(
        self, temp_log: Path, high_temp_metrics: HardwareMetrics
    ) -> None:
        """Test clearing alerts removes log file."""
        mgr = AlertManager(log_path=temp_log)
        mgr.check_thresholds(high_temp_metrics)

        assert temp_log.exists()

        mgr.clear_alerts()

        assert not temp_log.exists()

    def test_clear_nonexistent_alerts(self, temp_log: Path) -> None:
        """Test clearing when no alerts exist."""
        mgr = AlertManager(log_path=temp_log)
        mgr.clear_alerts()  # Should not raise
