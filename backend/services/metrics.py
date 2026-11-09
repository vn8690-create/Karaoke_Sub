"""
Custom metrics for Cloud Monitoring.

This module provides application-level metrics for tracking job processing,
worker performance, and external API usage. Metrics can be viewed in:
1. Cloud Logging (via structured log entries)
2. Cloud Monitoring (via log-based metrics or OpenTelemetry)

The metrics service uses a pragmatic approach:
- Always emits metrics as structured log entries (works immediately)
- Uses the same JSON format as Cloud Logging
- Can be enhanced with OpenTelemetry metrics exporters when available

Usage:
    from backend.services.metrics import metrics
    
    # Record a job completion
    metrics.record_job_completed("abc123", source="upload")
    
    # Record worker duration
    metrics.record_worker_duration("audio", 45.2, success=True)
    
    # Record external API call
    with metrics.time_external_api("modal"):
        response = await modal_client.separate_audio(...)
"""
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from backend.services.tracing import get_current_trace_id, get_current_span_id


logger = logging.getLogger("metrics")


@dataclass
class MetricLabels:
    """Common metric labels."""
    job_id: Optional[str] = None
    worker: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    api: Optional[str] = None
    operation: Optional[str] = None
    bucket: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class MetricsService:
    """
    Application metrics service.
    
    Emits metrics as structured log entries that can be:
    1. Queried directly in Cloud Logging
    2. Converted to Cloud Monitoring metrics via log-based metrics
    3. Exported via OpenTelemetry (when configured)
    """
    
    def __init__(self):
        """Initialize the metrics service."""
        self._logger = logging.getLogger("metrics")
        # Ensure metrics logger outputs at INFO level
        self._logger.setLevel(logging.INFO)
    
    def _emit_metric(self, metric_name: str, metric_type: str, value: float, labels: Dict[str, Any]) -> None:
        """
        Emit a metric as a structured log entry.
        
        The log format is designed to be easily parsed by Cloud Logging
        and converted to log-based metrics.
        
        Args:
            metric_name: Name of the metric (e.g., "jobs_total")
            metric_type: Type of metric (counter, histogram, gauge)
            value: Metric value
            labels: Metric labels/dimensions
        """
        # Add trace context if available
        trace_id = get_current_trace_id()
        span_id = get_current_span_id()
        
        # Build metric entry
        metric_entry = {
            "metric_name": metric_name,
            "metric_type": metric_type,
            "metric_value": value,
            **labels,
        }
        
        if trace_id:
            metric_entry["trace_id"] = trace_id
        if span_id:
            metric_entry["span_id"] = span_id
        
        # Emit as structured log entry
        # Use INFO level so metrics always show up
        self._logger.info(
            f"METRIC {metric_name}={value}",
            extra=metric_entry
        )
    
    # =========================================
    # Job Metrics
    # =========================================
    
    def record_job_created(self, job_id: str, source: str = "unknown") -> None:
        """
        Record a new job creation.
        
        Args:
            job_id: Job ID
            source: Job source (upload, url, search)
        """
        self._emit_metric(
            metric_name="jobs_total",
            metric_type="counter",
            value=1,
            labels={"job_id": job_id, "status": "created", "source": source}
        )
    
    def record_job_completed(self, job_id: str, source: str = "unknown") -> None:
        """
        Record a job completion.
        
        Args:
            job_id: Job ID
            source: Job source (upload, url, search)
        """
        self._emit_metric(
            metric_name="jobs_total",
            metric_type="counter",
            value=1,
            labels={"job_id": job_id, "status": "completed", "source": source}
        )
    
    def record_job_failed(self, job_id: str, source: str = "unknown", error: Optional[str] = None) -> None:
        """
        Record a job failure.
        
        Args:
            job_id: Job ID
            source: Job source (upload, url, search)
            error: Optional error message
        """
        labels = {"job_id": job_id, "status": "failed", "source": source}
        if error:
            labels["error"] = error[:200]  # Truncate long errors
        self._emit_metric(
            metric_name="jobs_total",
            metric_type="counter",
            value=1,
            labels=labels
        )
    
    def record_job_duration(self, job_id: str, duration_seconds: float, source: str = "unknown") -> None:
        """
        Record total job processing duration.
        
        Args:
            job_id: Job ID
            duration_seconds: Total processing time in seconds
            source: Job source (upload, url, search)
        """
        self._emit_metric(
            metric_name="job_duration_seconds",
            metric_type="histogram",
            value=duration_seconds,
            labels={"job_id": job_id, "source": source}
        )
    
    # =========================================
    # Worker Metrics
    # =========================================
    
    def record_worker_started(self, worker: str, job_id: str) -> None:
        """
        Record a worker invocation start.
        
        Args:
            worker: Worker name (audio, lyrics, screens, video, render_video)
            job_id: Job ID
        """
        self._emit_metric(
            metric_name="worker_invocations_total",
            metric_type="counter",
            value=1,
            labels={"worker": worker, "job_id": job_id, "status": "started"}
        )
    
    def record_worker_duration(self, worker: str, duration_seconds: float, success: bool, job_id: Optional[str] = None) -> None:
        """
        Record worker processing duration.
        
        Args:
            worker: Worker name
            duration_seconds: Processing time in seconds
            success: Whether worker completed successfully
            job_id: Optional job ID
        """
        labels = {
            "worker": worker,
            "success": str(success).lower(),
        }
        if job_id:
            labels["job_id"] = job_id
        
        self._emit_metric(
            metric_name="job_stage_duration_seconds",
            metric_type="histogram",
            value=duration_seconds,
            labels=labels
        )
        
        # Also emit a counter for success/failure tracking
        self._emit_metric(
            metric_name="worker_invocations_total",
            metric_type="counter",
            value=1,
            labels={"worker": worker, "success": str(success).lower(), "job_id": job_id or "unknown"}
        )
    
    # =========================================
    # GCS Metrics
    # =========================================
    
    def record_gcs_operation(
        self,
        operation: str,
        bucket: str,
        success: bool,
        size_bytes: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        job_id: Optional[str] = None,
    ) -> None:
        """
        Record a GCS operation.
        
        Args:
            operation: Operation type (upload, download, delete)
            bucket: GCS bucket name
            success: Whether operation succeeded
            size_bytes: Optional file size in bytes
            duration_seconds: Optional operation duration
            job_id: Optional job ID
        """
        labels = {
            "operation": operation,
            "bucket": bucket,
            "success": str(success).lower(),
        }
        if job_id:
            labels["job_id"] = job_id
        
        self._emit_metric(
            metric_name="gcs_operations_total",
            metric_type="counter",
            value=1,
            labels=labels
        )
        
        if size_bytes is not None:
            self._emit_metric(
                metric_name="gcs_operation_bytes",
                metric_type="histogram",
                value=size_bytes,
                labels={**labels, "operation": operation}
            )
        
        if duration_seconds is not None:
            self._emit_metric(
                metric_name="gcs_operation_duration_seconds",
                metric_type="histogram",
                value=duration_seconds,
                labels={**labels, "operation": operation}
            )
    
    # =========================================
    # External API Metrics
    # =========================================
    
    def record_external_api_call(
        self,
        api: str,
        success: bool,
        duration_seconds: float,
        job_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Record an external API call.
        
        Args:
            api: API name (modal, audioshake, genius, spotify)
            success: Whether call succeeded
            duration_seconds: API call duration
            job_id: Optional job ID
            error: Optional error message
        """
        labels = {
            "api": api,
            "success": str(success).lower(),
        }
        if job_id:
            labels["job_id"] = job_id
        if error:
            labels["error"] = error[:100]  # Truncate
        
        self._emit_metric(
            metric_name="external_api_calls_total",
            metric_type="counter",
            value=1,
            labels=labels
        )
        
        self._emit_metric(
            metric_name="external_api_duration_seconds",
            metric_type="histogram",
            value=duration_seconds,
            labels={"api": api, "success": str(success).lower()}
        )
    
    @contextmanager
    def time_external_api(self, api: str, job_id: Optional[str] = None):
        """
        Context manager to time an external API call.
        
        Usage:
            with metrics.time_external_api("modal", job_id) as timer:
                response = await client.call_api()
                timer.set_success(True)
        
        Args:
            api: API name
            job_id: Optional job ID
            
        Yields:
            Timer object with set_success() method
        """
        timer = _ApiTimer()
        start_time = time.time()
        
        try:
            yield timer
        except Exception as e:
            timer.set_success(False)
            timer.error = str(e)
            raise
        finally:
            duration = time.time() - start_time
            self.record_external_api_call(
                api=api,
                success=timer.success,
                duration_seconds=duration,
                job_id=job_id,
                error=timer.error,
            )
    
    @contextmanager
    def time_worker(self, worker: str, job_id: str):
        """
        Context manager to time a worker execution.
        
        Usage:
            with metrics.time_worker("audio", job_id) as timer:
                await process_audio()
                timer.set_success(True)
        
        Args:
            worker: Worker name
            job_id: Job ID
            
        Yields:
            Timer object with set_success() method
        """
        timer = _ApiTimer()
        self.record_worker_started(worker, job_id)
        start_time = time.time()
        
        try:
            yield timer
        except Exception as e:
            timer.set_success(False)
            raise
        finally:
            duration = time.time() - start_time
            self.record_worker_duration(
                worker=worker,
                duration_seconds=duration,
                success=timer.success,
                job_id=job_id,
            )


class _ApiTimer:
    """Helper class for tracking API call success state."""
    
    def __init__(self):
        self.success = True  # Assume success unless set otherwise
        self.error: Optional[str] = None
    
    def set_success(self, success: bool) -> None:
        self.success = success


# Global metrics instance
metrics = MetricsService()

