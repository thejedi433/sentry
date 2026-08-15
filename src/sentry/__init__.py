"""
Sentry - Raspberry Pi Hardware Monitor.

A command-line tool for monitoring CPU temperature, GPU temperature,
voltage levels, and throttling status on Raspberry Pi devices.
"""

from sentry.hardware import HardwareReader
from sentry.storage import Database
from sentry.config import Config, ConfigError
from sentry.alerts import AlertManager

__version__ = "0.1.0"
__all__ = [
    "HardwareReader",
    "Database",
    "Config",
    "ConfigError",
    "AlertManager",
]
