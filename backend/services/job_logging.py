"""
Job-aware logging utilities.

This module provides a context manager and logging handler that captures
Python logging output and forwards it to Firestore for real-time streaming
to the CLI.

Usage:
    with JobLogContext(job_id, worker="review") as log_context:
        # Any logging within this block will be captured and sent to Firestore
        logger.info("Processing...")  # This will be stored and streamed to CLI
"""
import logging
import threading
from typing import Optional
from contextlib import contextmanager
from datetime import datetime

from backend.services.firestore_service import FirestoreService


class JobLogHandler(logging.Handler):
    """
    A logging handler that forwards log records to Firestore for job tracking.
    
    This enables real-time log streaming to the CLI during long-running operations
    like lyrics correction, preview generation, etc.
    """
    
    def __init__(
        self,
        job_id: str,
        worker: str = "review",
        firestore: Optional[FirestoreService] = None,
        min_level: int = logging.INFO,
        batch_size: int = 1,  # Send immediately for real-time experience
    ):
        """
        Initialize the job log handler.
        
        Args:
            job_id: The job ID to associate logs with
            worker: Worker name (e.g., "review", "add-lyrics", "preview")
            firestore: FirestoreService instance (creates one if not provided)
            min_level: Minimum log level to capture (default INFO)
            batch_size: Number of logs to batch before sending (1 = immediate)
        """
        super().__init__()
        self.job_id = job_id
        self.worker = worker
        self.firestore = firestore or FirestoreService()
        self.min_level = min_level
        self.batch_size = batch_size
        self._log_buffer = []
        self._lock = threading.Lock()
        
        # Set the handler's level
        self.setLevel(min_level)
        
        # Create a formatter that extracts the useful parts
        self.setFormatter(logging.Formatter('%(message)s'))
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Process a log record and send it to Firestore.
        
        This method is called by the logging framework for each log message.
        """
        try:
            # Skip if below minimum level
            if record.levelno < self.min_level:
                return
            
            # Format the message
            message = self.format(record)
            
            # Truncate very long messages
            if len(message) > 1000:
                message = message[:997] + "..."
            
            # Create log entry
            log_entry = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'worker': self.worker,
                'message': message,
            }
            
            # Add to buffer
            with self._lock:
                self._log_buffer.append(log_entry)
                
                # Flush if batch size reached
                if len(self._log_buffer) >= self.batch_size:
                    self._flush_buffer()
                    
        except Exception:
            # Never let logging errors propagate
            self.handleError(record)
    
    def _flush_buffer(self) -> None:
        """Flush buffered logs to Firestore."""
        if not self._log_buffer:
            return
        
        try:
            for log_entry in self._log_buffer:
                self.firestore.append_worker_log(self.job_id, log_entry)
            self._log_buffer = []
        except Exception:
            # If Firestore fails, just clear buffer and continue
            self._log_buffer = []
    
    def flush(self) -> None:
        """Flush any remaining buffered logs."""
        with self._lock:
            self._flush_buffer()
    
    def close(self) -> None:
        """Clean up the handler."""
        self.flush()
        super().close()


@contextmanager
def job_log_context(
    job_id: str,
    worker: str = "review",
    logger_names: Optional[list] = None,
    min_level: int = logging.INFO,
):
    """
    Context manager that captures logs and forwards them to Firestore.
    
    This allows the CLI to see real-time logs from operations like
    add-lyrics, preview generation, etc.
    
    Args:
        job_id: Job ID to associate logs with
        worker: Worker name for log categorization
        logger_names: List of logger names to capture (None = capture common loggers)
        min_level: Minimum log level to capture
        
    Usage:
        with job_log_context(job_id, worker="add-lyrics"):
            # All logging in this block will be captured
            correction_operations.add_lyrics_source(...)
    """
    # Default loggers to capture - these cover most of our processing
    # Note: We intentionally DON'T include the root logger ('') to avoid
    # duplicate log entries since logs propagate up the logger hierarchy.
    # Only capture at the top-level package loggers.
    if logger_names is None:
        logger_names = [
            'backend.api.routes.review',
            'lyrics_transcriber',
            'karaoke_gen',
        ]
    
    # Create the handler
    handler = JobLogHandler(
        job_id=job_id,
        worker=worker,
        min_level=min_level,
    )
    
    # Add handler to all specified loggers
    loggers = []
    for name in logger_names:
        log = logging.getLogger(name) if name else logging.getLogger()
        log.addHandler(handler)
        loggers.append(log)
    
    try:
        # Log start
        handler.emit(logging.LogRecord(
            name='job_log_context',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg=f"🚀 Starting {worker} operation for job {job_id}",
            args=(),
            exc_info=None,
        ))
        
        yield handler
        
    finally:
        # Log completion
        handler.emit(logging.LogRecord(
            name='job_log_context',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg=f"✅ Completed {worker} operation for job {job_id}",
            args=(),
            exc_info=None,
        ))
        
        # Flush remaining logs
        handler.flush()
        
        # Remove handler from all loggers
        for log in loggers:
            log.removeHandler(handler)
        
        # Close handler
        handler.close()


class JobLogger:
    """
    A convenience class for direct logging to a job's log stream.
    
    Use this when you want to log specific messages without capturing
    all logging output.
    """
    
    def __init__(self, job_id: str, worker: str = "review"):
        """
        Initialize job logger.
        
        Args:
            job_id: Job ID to log to
            worker: Worker name for log categorization
        """
        self.job_id = job_id
        self.worker = worker
        self.firestore = FirestoreService()
    
    def _log(self, level: str, message: str) -> None:
        """Internal logging method."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'worker': self.worker,
            'message': message[:1000],
        }
        try:
            self.firestore.append_worker_log(self.job_id, log_entry)
        except Exception:
            pass  # Don't let logging errors propagate
    
    def info(self, message: str) -> None:
        """Log an INFO message."""
        self._log('INFO', message)
    
    def warning(self, message: str) -> None:
        """Log a WARNING message."""
        self._log('WARNING', message)
    
    def error(self, message: str) -> None:
        """Log an ERROR message."""
        self._log('ERROR', message)
    
    def debug(self, message: str) -> None:
        """Log a DEBUG message."""
        self._log('DEBUG', message)
