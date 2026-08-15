"""
SQLite storage for Sentry hardware metrics.

Stores timestamped readings in a local database at
~/.local/share/sentry/history.db for historical analysis.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from sentry.hardware import HardwareMetrics


class Database:
    """SQLite database for storing hardware metrics history.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize database connection.

        Args:
            db_path: Optional path to database file. Defaults to
                     ~/.local/share/sentry/history.db.
        """
        if db_path is None:
            db_path = Path.home() / ".local" / "share" / "sentry" / "history.db"
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    cpu_temp REAL,
                    gpu_temp REAL,
                    arm_voltage REAL,
                    core_voltage REAL,
                    throttled INTEGER,
                    throttle_status TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_readings_timestamp
                ON readings(timestamp)
            """
            )
            conn.commit()

    def store_reading(self, metrics: HardwareMetrics) -> int:
        """Store a hardware metrics reading.

        Args:
            metrics: HardwareMetrics instance to store.

        Returns:
            The ID of the inserted row.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO readings
                (timestamp, cpu_temp, gpu_temp, arm_voltage, core_voltage,
                 throttled, throttle_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics.timestamp,
                    metrics.cpu_temp,
                    metrics.gpu_temp,
                    metrics.arm_voltage,
                    metrics.core_voltage,
                    metrics.throttled,
                    metrics.throttle_status,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent_readings(
        self, limit: int = 10, minutes: Optional[int] = None
    ) -> list[HardwareMetrics]:
        """Get recent hardware readings.

        Args:
            limit: Maximum number of readings to return.
            minutes: Only return readings from the last N minutes.

        Returns:
            List of HardwareMetrics instances, newest first.
        """
        import time

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM readings"
            conditions = []
            params = []

            if minutes is not None:
                cutoff = time.time() - (minutes * 60)
                conditions.append("timestamp >= ?")
                params.append(cutoff)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                HardwareMetrics(
                    timestamp=row["timestamp"],
                    cpu_temp=row["cpu_temp"] or 0.0,
                    gpu_temp=row["gpu_temp"] or 0.0,
                    arm_voltage=row["arm_voltage"] or 0.0,
                    core_voltage=row["core_voltage"] or 0.0,
                    throttled=row["throttled"] or 0,
                    throttle_status=row["throttle_status"] or "unknown",
                )
                for row in rows
            ]

    def get_stats(
        self, minutes: int = 60
    ) -> dict[str, dict[str, Optional[float]]]:
        """Get statistics for recent readings.

        Args:
            minutes: Time window in minutes.

        Returns:
            Dictionary with min/max/avg for each metric.
        """
        import time

        cutoff = time.time() - (minutes * 60)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    MIN(cpu_temp) as cpu_min, MAX(cpu_temp) as cpu_max, AVG(cpu_temp) as cpu_avg,
                    MIN(gpu_temp) as gpu_min, MAX(gpu_temp) as gpu_max, AVG(gpu_temp) as gpu_avg,
                    MIN(arm_voltage) as arm_min, MAX(arm_voltage) as arm_max, AVG(arm_voltage) as arm_avg,
                    MIN(core_voltage) as core_min, MAX(core_voltage) as core_max, AVG(core_voltage) as core_avg
                FROM readings
                WHERE timestamp >= ?
            """,
                (cutoff,),
            )
            row = cursor.fetchone()

            return {
                "cpu_temp": {
                    "min": row[0],
                    "max": row[1],
                    "avg": row[2],
                },
                "gpu_temp": {
                    "min": row[3],
                    "max": row[4],
                    "avg": row[5],
                },
                "arm_voltage": {
                    "min": row[6],
                    "max": row[7],
                    "avg": row[8],
                },
                "core_voltage": {
                    "min": row[9],
                    "max": row[10],
                    "avg": row[11],
                },
            }

    def count_readings(self) -> int:
        """Get total number of readings in database.

        Returns:
            Count of readings.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM readings")
            return cursor.fetchone()[0]

    def clear_old_readings(self, days: int = 7) -> int:
        """Delete readings older than specified days.

        Args:
            days: Number of days to keep.

        Returns:
            Number of rows deleted.
        """
        import time

        cutoff = time.time() - (days * 24 * 60 * 60)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM readings WHERE timestamp < ?", (cutoff,)
            )
            conn.commit()
            return cursor.rowcount
