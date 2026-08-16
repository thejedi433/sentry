"""
Hardware metrics reader for Raspberry Pi.

Reads CPU temperature, GPU temperature, voltage levels, and throttling status
from vcgencmd and /sys filesystem on Raspberry Pi devices.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _find_vcgencmd() -> str:
    """Find vcgencmd binary in PATH or common locations.

    Returns:
        Path to vcgencmd binary, or 'vcgencmd' as fallback.
    """
    # Check PATH first
    path = shutil.which("vcgencmd")
    if path:
        return path
    # Check common locations
    for loc in ["/usr/bin/vcgencmd", "/opt/vc/bin/vcgencmd"]:
        if os.path.exists(loc):
            return loc
    return "vcgencmd"


@dataclass
class HardwareMetrics:
    """Container for hardware metrics readings.

    Attributes:
        cpu_temp: CPU temperature in Celsius.
        gpu_temp: GPU temperature in Celsius.
        arm_voltage: ARM voltage in Volts.
        core_voltage: Core voltage in Volts.
        throttled: Raw throttling status bitmask.
        throttle_status: Parsed throttle status description.
        timestamp: Unix timestamp of the reading.
    """

    cpu_temp: float
    gpu_temp: float
    arm_voltage: float
    core_voltage: float
    throttled: int
    throttle_status: str
    timestamp: float


class HardwareReader:
    """Read hardware metrics from Raspberry Pi.

    Uses vcgencmd for GPU metrics and /sys/class/thermal for CPU temperature.
    Gracefully handles missing vcgencmd or permission errors.

    Attributes:
        vcgencmd_path: Path to vcgencmd executable.
        thermal_zone: Path to thermal zone for CPU temperature.
    """

    def __init__(
        self,
        vcgencmd_path: Optional[str] = None,
        thermal_zone: str = "/sys/class/thermal/thermal_zone0/temp",
    ) -> None:
        """Initialize hardware reader.

        Args:
            vcgencmd_path: Path to vcgencmd binary (auto-detected if None).
            thermal_zone: Path to thermal zone temperature file.
        """
        self.vcgencmd_path = vcgencmd_path or _find_vcgencmd()
        self.thermal_zone = Path(thermal_zone)

    def _run_vcgencmd(self, command: str) -> Optional[str]:
        """Run vcgencmd command and return output.

        Args:
            command: vcgencmd command to run (e.g., 'measure_temp').

        Returns:
            Command output string or None if vcgencmd unavailable.
        """
        if not os.path.exists(self.vcgencmd_path):
            return None
        try:
            result = subprocess.run(
                [self.vcgencmd_path, command],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, OSError, PermissionError):
            return None

    def _read_thermal_zone(self) -> Optional[float]:
        """Read CPU temperature from thermal zone.

        Returns:
            Temperature in Celsius or None if unavailable.
        """
        if not self.thermal_zone.exists():
            return None
        try:
            content = self.thermal_zone.read_text().strip()
            # Thermal zone reports in millidegrees
            return float(content) / 1000.0
        except (OSError, ValueError, PermissionError):
            return None

    def _parse_vcgencmd_temp(self, output: Optional[str]) -> Optional[float]:
        """Parse temperature from vcgencmd output.

        Args:
            output: Raw vcgencmd output (e.g., 'temp=45.2'C').

        Returns:
            Temperature in Celsius or None if parsing fails.
        """
        if not output:
            return None
        match = re.search(r"temp=([\d.]+)", output)
        if match:
            return float(match.group(1))
        return None

    def _parse_vcgencmd_voltage(self, output: Optional[str]) -> Optional[float]:
        """Parse voltage from vcgencmd output.

        Args:
            output: Raw vcgencmd output (e.g., 'volt=1.20V').

        Returns:
            Voltage in Volts or None if parsing fails.
        """
        if not output:
            return None
        match = re.search(r"volt=([\d.]+)", output)
        if match:
            return float(match.group(1))
        return None

    def _parse_throttled(self, output: Optional[str]) -> tuple[int, str]:
        """Parse throttling status from vcgencmd output.

        Args:
            output: Raw vcgencmd output (e.g., 'throttled=0x0').

        Returns:
            Tuple of (raw_bitmask, status_description).
        """
        if not output:
            return (0, "unknown")

        match = re.search(r"throttled=0x([0-9a-fA-F]+)", output)
        if not match:
            return (0, "unknown")

        bitmask = int(match.group(1), 16)

        # Parse throttling bits
        # Bit 0: Under-voltage detected
        # Bit 1: ARM frequency capped
        # Bit 2: Currently throttled
        # Bit 3: Soft temperature limit active
        # Bit 16: Under-voltage occurred
        # Bit 17: ARM frequency capped occurred
        # Bit 18: Throttling occurred
        # Bit 19: Soft temperature limit occurred

        flags = []
        if bitmask & 0x1:
            flags.append("under-voltage")
        if bitmask & 0x2:
            flags.append("freq-capped")
        if bitmask & 0x4:
            flags.append("throttled")
        if bitmask & 0x8:
            flags.append("temp-limit")
        if bitmask & 0x10000:
            flags.append("uv-occurred")
        if bitmask & 0x20000:
            flags.append("freq-capped-occurred")
        if bitmask & 0x40000:
            flags.append("throttling-occurred")
        if bitmask & 0x80000:
            flags.append("temp-limit-occurred")

        if flags:
            status = ", ".join(flags)
        else:
            status = "normal"

        return (bitmask, status)

    def get_cpu_temp(self) -> Optional[float]:
        """Get CPU temperature.

        Returns:
            Temperature in Celsius or None if unavailable.
        """
        return self._read_thermal_zone()

    def get_gpu_temp(self) -> Optional[float]:
        """Get GPU temperature.

        Returns:
            Temperature in Celsius or None if unavailable.
        """
        output = self._run_vcgencmd("measure_temp")
        return self._parse_vcgencmd_temp(output)

    def get_arm_voltage(self) -> Optional[float]:
        """Get ARM core voltage.

        Returns:
            Voltage in Volts or None if unavailable.
        """
        output = self._run_vcgencmd("measure_volts ARM")
        return self._parse_vcgencmd_voltage(output)

    def get_core_voltage(self) -> Optional[float]:
        """Get core voltage.

        Returns:
            Voltage in Volts or None if unavailable.
        """
        output = self._run_vcgencmd("measure_volts Core")
        return self._parse_vcgencmd_voltage(output)

    def get_throttled(self) -> tuple[int, str]:
        """Get throttling status.

        Returns:
            Tuple of (raw_bitmask, status_description).
        """
        output = self._run_vcgencmd("get_throttled")
        return self._parse_throttled(output)

    def get_all_metrics(self) -> HardwareMetrics:
        """Get all hardware metrics in a single reading.

        Returns:
            HardwareMetrics dataclass with all readings.

        Raises:
            OSError: If no metrics are available (not on Pi).
        """
        import time

        cpu_temp = self.get_cpu_temp() or 0.0
        gpu_temp = self.get_gpu_temp() or 0.0
        arm_voltage = self.get_arm_voltage() or 0.0
        core_voltage = self.get_core_voltage() or 0.0
        throttled, throttle_status = self.get_throttled()

        return HardwareMetrics(
            cpu_temp=cpu_temp,
            gpu_temp=gpu_temp,
            arm_voltage=arm_voltage,
            core_voltage=core_voltage,
            throttled=throttled,
            throttle_status=throttle_status,
            timestamp=time.time(),
        )
