"""
Command-line interface for Sentry hardware monitor.

Provides commands for checking status, continuous monitoring,
viewing alerts, and managing configuration.
"""

import time
from typing import Optional

import click

from sentry import __version__
from sentry.alerts import AlertManager
from sentry.config import Config, ConfigError
from sentry.hardware import HardwareReader, HardwareMetrics
from sentry.storage import Database


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Sentry - Raspberry Pi Hardware Monitor.

    Monitor CPU/GPU temperature, voltage, and throttling status.
    """
    pass


@main.command()
def status() -> None:
    """Show current hardware status."""
    reader = HardwareReader()

    try:
        metrics = reader.get_all_metrics()
    except OSError as e:
        click.echo(f"Error reading hardware metrics: {e}", err=True)
        click.echo("Note: sentry is designed for Raspberry Pi devices.", err=True)
        raise SystemExit(1)

    click.echo("=== Sentry Hardware Status ===")
    click.echo(f"CPU Temperature:  {metrics.cpu_temp:.1f}°C")
    click.echo(f"GPU Temperature:  {metrics.gpu_temp:.1f}°C")
    click.echo(f"ARM Voltage:      {metrics.arm_voltage:.2f}V")
    click.echo(f"Core Voltage:     {metrics.core_voltage:.2f}V")
    click.echo(f"Throttled:        {metrics.throttle_status}")
    click.echo(f"Timestamp:        {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metrics.timestamp))}")

    # Store reading
    db = Database()
    db.store_reading(metrics)


@main.command()
@click.option("--interval", "-i", default=2, help="Update interval in seconds")
def monitor(interval: int) -> None:
    """Continuous monitoring mode.

    Displays real-time hardware metrics that update at the specified interval.
    Press Ctrl+C to exit.
    """
    reader = HardwareReader()
    db = Database()

    click.echo(f"Starting continuous monitoring (interval: {interval}s)")
    click.echo("Press Ctrl+C to exit\n")

    try:
        while True:
            # Clear screen and move cursor to top-left
            click.clear()

            try:
                metrics = reader.get_all_metrics()
            except OSError:
                click.echo("Error: Unable to read hardware metrics")
                click.echo("Note: sentry is designed for Raspberry Pi devices.")
                time.sleep(interval)
                continue

            # Store reading
            db.store_reading(metrics)

            # Check for alerts
            config = Config.load()
            alert_mgr = AlertManager(config)
            alerts = alert_mgr.check_thresholds(metrics)

            # Display metrics
            click.echo("=== Sentry Monitor ===")
            click.echo(f"CPU Temperature:  {metrics.cpu_temp:.1f}°C")
            click.echo(f"GPU Temperature:  {metrics.gpu_temp:.1f}°C")
            click.echo(f"ARM Voltage:      {metrics.arm_voltage:.2f}V")
            click.echo(f"Core Voltage:     {metrics.core_voltage:.2f}V")
            click.echo(f"Throttled:        {metrics.throttle_status}")
            click.echo(f"Last update:      {time.strftime('%H:%M:%S')}")
            click.echo()

            if alerts:
                click.echo(click.style("⚠ ALERTS:", fg="red"))
                for alert in alerts:
                    click.echo(click.style(f"  • {alert}", fg="red"))
            else:
                click.echo(click.style("✓ All metrics normal", fg="green"))

            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo("\nMonitoring stopped.")


@main.command()
@click.option("--limit", "-l", default=20, help="Number of alerts to show")
@click.option("--clear", "-c", is_flag=True, help="Clear alerts log")
def alerts(limit: int, clear: bool) -> None:
    """Show recent alerts.

    Displays threshold violations logged by sentry.
    """
    config = Config.load()
    alert_mgr = AlertManager(config)

    if clear:
        alert_mgr.clear_alerts()
        click.echo("Alerts log cleared.")
        return

    recent = alert_mgr.get_recent_alerts(limit)

    if not recent:
        click.echo("No alerts recorded.")
    else:
        click.echo(f"=== Recent Alerts (last {len(recent)}) ===")
        for alert in recent:
            click.echo(alert)


@main.command()
@click.option("--cpu-temp", type=float, help="CPU temperature threshold (°C)")
@click.option("--gpu-temp", type=float, help="GPU temperature threshold (°C)")
@click.option("--arm-voltage", type=float, help="Minimum ARM voltage (V)")
@click.option("--core-voltage", type=float, help="Minimum core voltage (V)")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--reset", is_flag=True, help="Reset to defaults")
def config(
    cpu_temp: Optional[float],
    gpu_temp: Optional[float],
    arm_voltage: Optional[float],
    core_voltage: Optional[float],
    show: bool,
    reset: bool,
) -> None:
    """Manage configuration thresholds.

    Without options, shows current configuration.
    Use --show to display without modifying.
    Use --reset to restore defaults.
    Use other options to set specific thresholds.
    """
    config_path = Config().config_path

    if reset:
        if config_path.exists():
            config_path.unlink()
        cfg = Config()
        cfg.save()
        click.echo("Configuration reset to defaults.")
        click.echo(f"Config file: {config_path}")
    elif show or (cpu_temp is None and gpu_temp is None and arm_voltage is None and core_voltage is None):
        try:
            cfg = Config.load()
        except ConfigError as e:
            click.echo(f"Error loading config: {e}", err=True)
            raise SystemExit(1)

        click.echo("=== Sentry Configuration ===")
        click.echo(f"Config file: {config_path}")
        click.echo(f"CPU Temp Threshold:  {cfg.cpu_temp_threshold}°C")
        click.echo(f"GPU Temp Threshold:  {cfg.gpu_temp_threshold}°C")
        click.echo(f"ARM Voltage Min:     {cfg.arm_voltage_min}V")
        click.echo(f"Core Voltage Min:    {cfg.core_voltage_min}V")
    else:
        try:
            cfg = Config.load()
        except ConfigError:
            cfg = Config()

        # Update specified values
        if cpu_temp is not None:
            cfg.cpu_temp_threshold = cpu_temp
        if gpu_temp is not None:
            cfg.gpu_temp_threshold = gpu_temp
        if arm_voltage is not None:
            cfg.arm_voltage_min = arm_voltage
        if core_voltage is not None:
            cfg.core_voltage_min = core_voltage

        # Validate
        errors = cfg.validate()
        if errors:
            click.echo("Validation errors:", err=True)
            for error in errors:
                click.echo(f"  • {error}", err=True)
            raise SystemExit(1)

        cfg.save()
        click.echo("Configuration saved.")
        click.echo(f"Config file: {cfg.config_path}")


if __name__ == "__main__":
    main()
