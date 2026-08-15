"""
Alert management for Sentry.

Monitors hardware metrics against configurable thresholds and
logs alerts to ~/.local/share/sentry/alerts.log.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sentry.config import Config
from sentry.hardware import HardwareMetrics


class AlertManager:
    """Manages alert logging for threshold violations.

    Attributes:
        config: Configuration with threshold values.
        log_path: Path to alerts log file.
        logger: Configured logger for alerts.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        log_path: Optional[Path] = None,
    ) -> None:
        """Initialize alert manager.

        Args:
            config: Configuration with thresholds. Defaults to loaded config.
            log_path: Optional path to alerts log. Defaults to
                      ~/.local/share/sentry/alerts.log.
        """
        self.config = config or Config.load()
        if log_path is None:
            log_path = Path.home() / ".local" / "share" / "sentry" / "alerts.log"
        self.log_path = log_path
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Set up the alerts logger."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("sentry.alerts")
        self.logger.setLevel(logging.WARNING)

        # File handler
        handler = logging.FileHandler(self.log_path)
        handler.setLevel(logging.WARNING)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def check_thresholds(self, metrics: HardwareMetrics) -> list[str]:
        """Check metrics against thresholds.

        Args:
            metrics: HardwareMetrics to check.

        Returns:
            List of alert messages for violations.
        """
        alerts = []

        # Check CPU temperature
        if metrics.cpu_temp > self.config.cpu_temp_threshold:
            msg = (
                f"HIGH_CPU_TEMP: CPU temperature {metrics.cpu_temp:.1f}°C "
                f"exceeds threshold {self.config.cpu_temp_threshold}°C"
            )
            alerts.append(msg)
            self.logger.warning(msg)

        # Check GPU temperature
        if metrics.gpu_temp > self.config.gpu_temp_threshold:
            msg = (
                f"HIGH_GPU_TEMP: GPU temperature {metrics.gpu_temp:.1f}°C "
                f"exceeds threshold {self.config.gpu_temp_threshold}°C"
            )
            alerts.append(msg)
            self.logger.warning(msg)

        # Check ARM voltage
        if metrics.arm_voltage > 0 and metrics.arm_voltage < self.config.arm_voltage_min:
            msg = (
                f"LOW_ARM_VOLTAGE: ARM voltage {metrics.arm_voltage:.2f}V "
                f"below threshold {self.config.arm_voltage_min}V"
            )
            alerts.append(msg)
            self.logger.warning(msg)

        # Check core voltage
        if (
            metrics.core_voltage > 0
            and metrics.core_voltage < self.config.core_voltage_min
        ):
            msg = (
                f"LOW_CORE_VOLTAGE: Core voltage {metrics.core_voltage:.2f}V "
                f"below threshold {self.config.core_voltage_min}V"
            )
            alerts.append(msg)
            self.logger.warning(msg)

        # Check throttling status
        if metrics.throttled != 0:
            msg = f"THROTTLED: {metrics.throttle_status}"
            alerts.append(msg)
            self.logger.warning(msg)

        return alerts

    def get_recent_alerts(self, limit: int = 20) -> list[str]:
        """Get recent alerts from log file.

        Args:
            limit: Maximum number of alerts to return.

        Returns:
            List of recent alert messages.
        """
        if not self.log_path.exists():
            return []

        try:
            content = self.log_path.read_text()
            lines = content.strip().split("\n")
            # Return last N non-empty lines
            alerts = [line for line in lines if line.strip()][-limit:]
            return alerts
        except Exception:
            return []

    def clear_alerts(self) -> None:
        """Clear the alerts log file."""
        if self.log_path.exists():
            self.log_path.unlink()
