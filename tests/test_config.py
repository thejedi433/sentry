"""
Tests for sentry.config module.

Tests configuration loading, saving, validation, and error handling.
"""

import tempfile
from pathlib import Path

import pytest

from sentry.config import Config, ConfigError


class TestConfigDefaults:
    """Test default configuration values."""

    def test_default_cpu_temp_threshold(self) -> None:
        """Test default CPU temperature threshold is 70.0."""
        config = Config()
        assert config.cpu_temp_threshold == 70.0

    def test_default_gpu_temp_threshold(self) -> None:
        """Test default GPU temperature threshold is 70.0."""
        config = Config()
        assert config.gpu_temp_threshold == 70.0

    def test_default_arm_voltage_min(self) -> None:
        """Test default ARM voltage minimum is 1.2."""
        config = Config()
        assert config.arm_voltage_min == 1.2

    def test_default_core_voltage_min(self) -> None:
        """Test default core voltage minimum is 1.2."""
        config = Config()
        assert config.core_voltage_min == 1.2

    def test_default_config_path(self) -> None:
        """Test default config path is ~/.config/sentry/config.toml."""
        config = Config()
        assert config.config_path == Path.home() / ".config" / "sentry" / "config.toml"


class TestConfigLoad:
    """Test configuration loading."""

    def test_load_nonexistent_file(self) -> None:
        """Test loading when config file doesn't exist returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = Config.load(config_path)

            assert config.cpu_temp_threshold == 70.0
            assert config.gpu_temp_threshold == 70.0
            assert config.arm_voltage_min == 1.2
            assert config.core_voltage_min == 1.2

    def test_load_valid_file(self) -> None:
        """Test loading valid config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
[thresholds]
cpu_temp = 75.0
gpu_temp = 80.0
arm_voltage = 1.1
core_voltage = 1.15
""")
            config = Config.load(config_path)

            assert config.cpu_temp_threshold == 75.0
            assert config.gpu_temp_threshold == 80.0
            assert config.arm_voltage_min == 1.1
            assert config.core_voltage_min == 1.15

    def test_load_partial_file(self) -> None:
        """Test loading config file with only some values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
[thresholds]
cpu_temp = 85.0
""")
            config = Config.load(config_path)

            assert config.cpu_temp_threshold == 85.0
            assert config.gpu_temp_threshold == 70.0  # default
            assert config.arm_voltage_min == 1.2  # default

    def test_load_invalid_toml(self) -> None:
        """Test loading invalid TOML raises ConfigError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("invalid toml {{{")

            with pytest.raises(ConfigError):
                Config.load(config_path)


class TestConfigSave:
    """Test configuration saving."""

    def test_save_creates_directory(self) -> None:
        """Test saving creates config directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "config" / "config.toml"
            config = Config(config_path=config_path)
            config.save()

            assert config_path.exists()

    def test_save_writes_values(self) -> None:
        """Test saving writes correct values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = Config(
                config_path=config_path,
                cpu_temp_threshold=80.0,
                gpu_temp_threshold=75.0,
                arm_voltage_min=1.1,
                core_voltage_min=1.15,
            )
            config.save()

            content = config_path.read_text()
            assert "cpu_temp = 80.0" in content
            assert "gpu_temp = 75.0" in content
            assert "arm_voltage = 1.1" in content
            assert "core_voltage = 1.15" in content

    def test_save_and_reload(self) -> None:
        """Test saving and reloading preserves values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config1 = Config(
                config_path=config_path,
                cpu_temp_threshold=82.0,
                gpu_temp_threshold=78.0,
                arm_voltage_min=1.05,
                core_voltage_min=1.08,
            )
            config1.save()

            config2 = Config.load(config_path)
            assert config2.cpu_temp_threshold == 82.0
            assert config2.gpu_temp_threshold == 78.0
            assert config2.arm_voltage_min == 1.05
            assert config2.core_voltage_min == 1.08


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_valid_config(self) -> None:
        """Test validation returns empty list for valid config."""
        config = Config()
        errors = config.validate()
        assert errors == []

    def test_validate_cpu_temp_too_low(self) -> None:
        """Test validation catches CPU temp below 0."""
        config = Config(cpu_temp_threshold=-10.0)
        errors = config.validate()
        assert any("cpu_temp" in e for e in errors)

    def test_validate_cpu_temp_too_high(self) -> None:
        """Test validation catches CPU temp above 100."""
        config = Config(cpu_temp_threshold=150.0)
        errors = config.validate()
        assert any("cpu_temp" in e for e in errors)

    def test_validate_gpu_temp_too_low(self) -> None:
        """Test validation catches GPU temp below 0."""
        config = Config(gpu_temp_threshold=-5.0)
        errors = config.validate()
        assert any("gpu_temp" in e for e in errors)

    def test_validate_gpu_temp_too_high(self) -> None:
        """Test validation catches GPU temp above 100."""
        config = Config(gpu_temp_threshold=120.0)
        errors = config.validate()
        assert any("gpu_temp" in e for e in errors)

    def test_validate_arm_voltage_too_low(self) -> None:
        """Test validation catches ARM voltage below 0.8."""
        config = Config(arm_voltage_min=0.5)
        errors = config.validate()
        assert any("arm_voltage" in e for e in errors)

    def test_validate_arm_voltage_too_high(self) -> None:
        """Test validation catches ARM voltage above 1.5."""
        config = Config(arm_voltage_min=2.0)
        errors = config.validate()
        assert any("arm_voltage" in e for e in errors)

    def test_validate_core_voltage_too_low(self) -> None:
        """Test validation catches core voltage below 0.8."""
        config = Config(core_voltage_min=0.5)
        errors = config.validate()
        assert any("core_voltage" in e for e in errors)

    def test_validate_core_voltage_too_high(self) -> None:
        """Test validation catches core voltage above 1.5."""
        config = Config(core_voltage_min=2.0)
        errors = config.validate()
        assert any("core_voltage" in e for e in errors)

    def test_validate_multiple_errors(self) -> None:
        """Test validation returns all errors."""
        config = Config(
            cpu_temp_threshold=150.0,
            gpu_temp_threshold=-10.0,
            arm_voltage_min=0.5,
        )
        errors = config.validate()
        assert len(errors) >= 3
