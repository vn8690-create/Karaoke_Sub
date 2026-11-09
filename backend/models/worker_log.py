"""
Worker log entry model for subcollection storage.

This module defines the LogEntry model for storing worker logs in a Firestore
subcollection instead of an embedded array. This avoids the 1MB document size
limit that caused job 501258e1 to fail when logs reached 1.26 MB.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import uuid


# Default TTL for log entries (30 days)
DEFAULT_LOG_TTL_DAYS = 30


@dataclass
class WorkerLogEntry:
    """
    Worker log entry for Firestore subcollection storage.

    Stored at: jobs/{job_id}/logs/{log_id}

    This model is separate from the legacy LogEntry (in job.py) which is
    stored as an embedded array in the job document. This new model supports
    the subcollection approach with TTL and richer metadata.
    """
    # Core fields (required)
    timestamp: datetime
    level: str  # "DEBUG", "INFO", "WARNING", "ERROR"
    worker: str  # "audio", "lyrics", "screens", "video", "render", "distribution"
    message: str

    # Identifiers
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""  # Set when writing to Firestore

    # TTL for automatic cleanup
    ttl_expiry: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=DEFAULT_LOG_TTL_DAYS)
    )

    # Optional metadata for debugging
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        job_id: str,
        worker: str,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_days: int = DEFAULT_LOG_TTL_DAYS
    ) -> "WorkerLogEntry":
        """
        Factory method to create a new log entry.

        Args:
            job_id: Job ID this log belongs to
            worker: Worker name (audio, lyrics, screens, video, render, distribution)
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Log message (truncated to 1000 chars)
            metadata: Optional additional metadata
            ttl_days: Days until log expires (default 30)

        Returns:
            New WorkerLogEntry instance
        """
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            job_id=job_id,
            timestamp=now,
            level=level.upper(),
            worker=worker,
            message=message[:1000],  # Truncate long messages
            metadata=metadata,
            ttl_expiry=now + timedelta(days=ttl_days)
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for Firestore storage.

        Returns:
            Dictionary representation for Firestore
        """
        result = {
            "id": self.id,
            "job_id": self.job_id,
            "timestamp": self.timestamp,
            "level": self.level,
            "worker": self.worker,
            "message": self.message,
            "ttl_expiry": self.ttl_expiry
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Convert to legacy format for backward compatibility with API responses.

        The existing API returns logs in this format:
        {"timestamp": "...", "level": "INFO", "worker": "audio", "message": "..."}

        Returns:
            Dictionary in legacy format
        """
        # Format timestamp: use "Z" suffix for UTC, isoformat() for others
        if self.timestamp.tzinfo is None:
            # Naive datetime - use as-is
            timestamp_str = self.timestamp.isoformat()
        elif self.timestamp.utcoffset() == timedelta(0):
            # UTC datetime - replace +00:00 with Z for cleaner format
            timestamp_str = self.timestamp.replace(tzinfo=None).isoformat() + "Z"
        else:
            # Non-UTC timezone-aware - use full isoformat with offset
            timestamp_str = self.timestamp.isoformat()

        return {
            "timestamp": timestamp_str,
            "level": self.level,
            "worker": self.worker,
            "message": self.message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerLogEntry":
        """
        Create from Firestore document data.

        Args:
            data: Dictionary from Firestore document

        Returns:
            WorkerLogEntry instance
        """
        # Handle timestamp conversion (Firestore returns datetime objects)
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            # Parse ISO format string
            timestamp = datetime.fromisoformat(timestamp.rstrip("Z")).replace(tzinfo=timezone.utc)

        ttl_expiry = data.get("ttl_expiry")
        if isinstance(ttl_expiry, str):
            ttl_expiry = datetime.fromisoformat(ttl_expiry.rstrip("Z")).replace(tzinfo=timezone.utc)
        elif ttl_expiry is None:
            # Default TTL if not set
            ttl_expiry = datetime.now(timezone.utc) + timedelta(days=DEFAULT_LOG_TTL_DAYS)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            job_id=data.get("job_id", ""),
            timestamp=timestamp or datetime.now(timezone.utc),
            level=data.get("level", "INFO"),
            worker=data.get("worker", "unknown"),
            message=data.get("message", ""),
            metadata=data.get("metadata"),
            ttl_expiry=ttl_expiry
        )
