"""
Tests for sentry.storage module.

Tests SQLite database operations for storing and retrieving
hardware metrics history.
"""

import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest

from sentry.hardware import HardwareMetrics
from sentry.storage import Database


@pytest.fixture
def temp_db() -> Generator[Database, None, None]:
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with Database(db_path) as db:
            yield db


@pytest.fixture
def sample_metrics() -> HardwareMetrics:
    """Create sample hardware metrics for testing."""
    return HardwareMetrics(
        cpu_temp=45.0,
        gpu_temp=50.0,
        arm_voltage=1.2,
        core_voltage=1.2,
        throttled=0,
        throttle_status="normal",
        timestamp=time.time(),
    )


class TestDatabaseInit:
    """Test database initialization."""

    def test_init_creates_file(self, temp_db: Database) -> None:
        """Test database file is created."""
        assert temp_db.db_path.exists()

    def test_init_creates_table(self, temp_db: Database) -> None:
        """Test readings table is created."""
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='readings'"
            )
            assert cursor.fetchone() is not None
            conn.commit()

    def test_init_creates_index(self, temp_db: Database) -> None:
        """Test timestamp index is created."""
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_readings_timestamp'"
            )
            assert cursor.fetchone() is not None
            conn.commit()

    def test_default_path(self) -> None:
        """Test default database path."""
        db = Database()
        assert db.db_path == Path.home() / ".local" / "share" / "sentry" / "history.db"
        db.close()


class TestStoreReading:
    """Test storing readings."""

    def test_store_reading(self, temp_db: Database, sample_metrics: HardwareMetrics) -> None:
        """Test storing a single reading."""
        row_id = temp_db.store_reading(sample_metrics)
        assert row_id == 1

    def test_store_multiple_readings(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test storing multiple readings."""
        temp_db.store_reading(sample_metrics)
        temp_db.store_reading(sample_metrics)
        temp_db.store_reading(sample_metrics)

        count = temp_db.count_readings()
        assert count == 3

    def test_store_reading_values(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test stored values are correct."""
        temp_db.store_reading(sample_metrics)

        with sqlite3.connect(temp_db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM readings")
            row = cursor.fetchone()

            assert row["cpu_temp"] == 45.0
            assert row["gpu_temp"] == 50.0
            assert row["arm_voltage"] == 1.2
            assert row["core_voltage"] == 1.2
            assert row["throttled"] == 0
            assert row["throttle_status"] == "normal"
            conn.commit()


class TestGetRecentReadings:
    """Test retrieving recent readings."""

    def test_get_recent_empty_db(self, temp_db: Database) -> None:
        """Test getting readings from empty database."""
        readings = temp_db.get_recent_readings(limit=10)
        assert readings == []

    def test_get_recent_limit(self, temp_db: Database, sample_metrics: HardwareMetrics) -> None:
        """Test getting limited number of readings."""
        for _ in range(5):
            temp_db.store_reading(sample_metrics)

        readings = temp_db.get_recent_readings(limit=3)
        assert len(readings) == 3

    def test_get_recent_ordering(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test readings are returned newest first."""
        # Store readings with different timestamps
        m1 = HardwareMetrics(**{**sample_metrics.__dict__, "timestamp": 100.0})
        m2 = HardwareMetrics(**{**sample_metrics.__dict__, "timestamp": 200.0})
        m3 = HardwareMetrics(**{**sample_metrics.__dict__, "timestamp": 300.0})

        temp_db.store_reading(m1)
        temp_db.store_reading(m2)
        temp_db.store_reading(m3)

        readings = temp_db.get_recent_readings(limit=10)

        assert readings[0].timestamp == 300.0
        assert readings[1].timestamp == 200.0
        assert readings[2].timestamp == 100.0

    def test_get_recent_minutes_filter(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test filtering by minutes."""
        # Current time reading
        temp_db.store_reading(sample_metrics)

        # Old reading (1 hour ago)
        old_metrics = HardwareMetrics(
            **{**sample_metrics.__dict__, "timestamp": time.time() - 3600}
        )
        temp_db.store_reading(old_metrics)

        readings = temp_db.get_recent_readings(limit=10, minutes=5)
        assert len(readings) == 1
        assert readings[0].timestamp > time.time() - 300


class TestGetStats:
    """Test statistics calculation."""

    def test_get_stats_empty_db(self, temp_db: Database) -> None:
        """Test stats from empty database."""
        stats = temp_db.get_stats(minutes=60)

        assert stats["cpu_temp"]["min"] is None
        assert stats["cpu_temp"]["max"] is None
        assert stats["cpu_temp"]["avg"] is None

    def test_get_stats_single_reading(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test stats with single reading."""
        temp_db.store_reading(sample_metrics)
        stats = temp_db.get_stats(minutes=60)

        assert stats["cpu_temp"]["min"] == 45.0
        assert stats["cpu_temp"]["max"] == 45.0
        assert stats["cpu_temp"]["avg"] == 45.0

    def test_get_stats_multiple_readings(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test stats with multiple readings."""
        m1 = HardwareMetrics(**{**sample_metrics.__dict__, "cpu_temp": 40.0})
        m2 = HardwareMetrics(**{**sample_metrics.__dict__, "cpu_temp": 50.0})
        m3 = HardwareMetrics(**{**sample_metrics.__dict__, "cpu_temp": 60.0})

        temp_db.store_reading(m1)
        temp_db.store_reading(m2)
        temp_db.store_reading(m3)

        stats = temp_db.get_stats(minutes=60)

        assert stats["cpu_temp"]["min"] == 40.0
        assert stats["cpu_temp"]["max"] == 60.0
        assert stats["cpu_temp"]["avg"] == 50.0

    def test_get_stats_all_metrics(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test stats for all metrics."""
        temp_db.store_reading(sample_metrics)
        stats = temp_db.get_stats(minutes=60)

        assert "cpu_temp" in stats
        assert "gpu_temp" in stats
        assert "arm_voltage" in stats
        assert "core_voltage" in stats


class TestCountReadings:
    """Test reading count."""

    def test_count_empty_db(self, temp_db: Database) -> None:
        """Test count on empty database."""
        count = temp_db.count_readings()
        assert count == 0

    def test_count_with_readings(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test count with readings."""
        for _ in range(7):
            temp_db.store_reading(sample_metrics)

        count = temp_db.count_readings()
        assert count == 7


class TestClearOldReadings:
    """Test clearing old readings."""

    def test_clear_old_empty_db(self, temp_db: Database) -> None:
        """Test clearing old readings from empty database."""
        deleted = temp_db.clear_old_readings(days=7)
        assert deleted == 0

    def test_clear_old_recent_readings(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test that recent readings are not deleted."""
        temp_db.store_reading(sample_metrics)

        deleted = temp_db.clear_old_readings(days=7)
        assert deleted == 0

        count = temp_db.count_readings()
        assert count == 1

    def test_clear_old_old_readings(
        self, temp_db: Database, sample_metrics: HardwareMetrics
    ) -> None:
        """Test that old readings are deleted."""
        # Add old reading (10 days ago)
        old_metrics = HardwareMetrics(
            **{**sample_metrics.__dict__, "timestamp": time.time() - (10 * 24 * 3600)}
        )
        temp_db.store_reading(old_metrics)

        deleted = temp_db.clear_old_readings(days=7)
        assert deleted == 1

        count = temp_db.count_readings()
        assert count == 0


class TestResourceManagement:
    """Test proper resource cleanup to avoid warnings."""

    def test_database_close_method(self, sample_metrics: HardwareMetrics) -> None:
        """Test Database has close method that properly closes connections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            
            # Store some data
            db.store_reading(sample_metrics)
            
            # Close should not raise
            db.close()
            
            # After close, operations should either work (reopen) or fail gracefully
            # For now, just verify close() exists and is callable
            assert hasattr(db, 'close')

    def test_database_context_manager(self, sample_metrics: HardwareMetrics) -> None:
        """Test Database can be used as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Should be able to use with statement
            with Database(db_path) as db:
                db.store_reading(sample_metrics)
                count = db.count_readings()
                assert count == 1
            
            # After exiting context, database should be properly closed
            # Verify we can reopen it (no locks or corruption)
            db2 = Database(db_path)
            count = db2.count_readings()
            assert count == 1
            db2.close()

    def test_no_resource_warnings_on_multiple_operations(
        self, sample_metrics: HardwareMetrics
    ) -> None:
        """Test that multiple operations don't leak resources."""
        import warnings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Capture warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                with Database(db_path) as db:
                    # Multiple operations
                    for _ in range(5):
                        db.store_reading(sample_metrics)
                    
                    db.get_recent_readings()
                    db.get_stats()
                    db.count_readings()
                
                # Check for ResourceWarning
                resource_warnings = [
                    warning for warning in w 
                    if issubclass(warning.category, ResourceWarning)
                ]
                assert len(resource_warnings) == 0, \
                    f"Found {len(resource_warnings)} ResourceWarnings"
