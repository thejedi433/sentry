# sentry

Raspberry Pi hardware monitoring tool for tracking CPU/GPU temperature, voltage levels, and throttling status.

## Features

- **Real-time monitoring**: Track CPU temperature, GPU temperature, ARM voltage, and core voltage
- **Throttling detection**: Monitor and alert on throttling events
- **Configurable thresholds**: Set custom alert thresholds for each metric
- **Historical data**: SQLite storage for metrics history and trend analysis
- **Alert logging**: Automatic logging of threshold violations
- **CLI interface**: Simple commands for status, continuous monitoring, and configuration
- **Dashboard integration**: Optional integration with web dashboards

## Requirements

- Raspberry Pi (tested on Pi 4)
- Python 3.11+
- `vcgencmd` (pre-installed on Raspberry Pi OS)

**Note**: sentry is designed for Raspberry Pi devices. On other systems, it will run but report 0 values for hardware metrics since `vcgencmd` is only available on Raspberry Pi.

## Installation

### From source

```bash
git clone https://github.com/thejedi433/sentry.git
cd sentry
pip install -e .
```

### With development dependencies

```bash
pip install -e ".[dev]"
```

### Docker (optional)

```bash
docker build -t sentry .
docker run --rm sentry status
```

**Note**: Docker support is optional and primarily useful for testing the CLI structure. Hardware metrics require direct access to Pi hardware.

## Usage

### Check current status

```bash
sentry status
```

Output:
```
=== Sentry Hardware Status ===
CPU Temperature:  45.0°C
GPU Temperature:  50.0°C
ARM Voltage:      1.20V
Core Voltage:     1.20V
Throttled:        normal
Timestamp:        2026-08-15 10:30:00
```

### Continuous monitoring

```bash
sentry monitor --interval 2
```

Press `Ctrl+C` to exit monitoring mode.

### View alerts

```bash
sentry alerts              # Show recent alerts
sentry alerts --limit 50   # Show last 50 alerts
sentry alerts --clear      # Clear alerts log
```

### View history and statistics

```bash
sentry history                  # Show last 10 readings
sentry history --limit 20       # Show last 20 readings
sentry history --minutes 30     # Show readings from last 30 minutes

sentry stats                    # Show min/max/avg for last hour
sentry stats --minutes 1440     # Show stats for last 24 hours
```

### Manage configuration

```bash
sentry config --show                # Show current config
sentry config --cpu-temp 75.0       # Set CPU threshold
sentry config --gpu-temp 80.0       # Set GPU threshold
sentry config --arm-voltage 1.1     # Set min ARM voltage
sentry config --core-voltage 1.1    # Set min core voltage
sentry config --reset               # Reset to defaults
```

Configuration is stored in `~/.config/sentry/config.toml`.

## Default Thresholds

| Metric | Default Threshold |
|--------|------------------|
| CPU Temperature | 70°C |
| GPU Temperature | 70°C |
| ARM Voltage (min) | 1.2V |
| Core Voltage (min) | 1.2V |

## File Locations

| File | Purpose |
|------|---------|
| `~/.config/sentry/config.toml` | Configuration thresholds |
| `~/.local/share/sentry/history.db` | SQLite database with metrics history |
| `~/.local/share/sentry/alerts.log` | Alert log file |

## API Usage

```python
from sentry import HardwareReader, Database, Config, AlertManager

# Read hardware metrics
reader = HardwareReader()
metrics = reader.get_all_metrics()
print(f"CPU: {metrics.cpu_temp}°C")

# Store in database
db = Database()
db.store_reading(metrics)

# Check alerts
config = Config.load()
alert_mgr = AlertManager(config)
alerts = alert_mgr.check_thresholds(metrics)
```

## Dashboard Integration

sentry integrates with the dashboard kiosk system to display hardware metrics:

```python
from sentry import HardwareReader

reader = HardwareReader()
metrics = reader.get_all_metrics()

# Add to dashboard response
response = {
    "cpu_temp": metrics.cpu_temp,
    "gpu_temp": metrics.gpu_temp,
    "arm_voltage": metrics.arm_voltage,
    "throttled": metrics.throttle_status != "normal",
}
```

## Development

### Running tests

```bash
pytest
```

### Running tests with coverage

```bash
pytest --cov=sentry --cov-report=html
```

### Project structure

```
sentry/
├── src/sentry/
│   ├── __init__.py      # Package exports
│   ├── hardware.py      # Hardware metrics reader
│   ├── storage.py       # SQLite database operations
│   ├── config.py        # Configuration management
│   ├── alerts.py        # Alert management
│   └── cli.py           # Click CLI interface
├── tests/
│   ├── test_hardware.py
│   ├── test_storage.py
│   ├── test_config.py
│   ├── test_alerts.py
│   └── test_cli.py
├── .github/workflows/
│   └── ci.yml           # GitHub Actions CI
├── Dockerfile           # Optional Docker build
├── pyproject.toml
└── README.md
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest`
4. Submit a pull request

## Troubleshooting

### "Error reading hardware metrics"

- Ensure you're running on a Raspberry Pi
- Check that vcgencmd is available: `/opt/vc/bin/vcgencmd version`
- Run with appropriate permissions if needed

### Permission denied errors

- The user may need to be added to the `video` group: `sudo usermod -aG video $USER`
- Log out and back in for group changes to take effect

### No alerts appearing

- Check that thresholds are set appropriately: `sentry config --show`
- Verify the alerts log exists: `~/.local/share/sentry/alerts.log`
