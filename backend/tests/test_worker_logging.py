"""
Unit tests for backend/workers/worker_logging.py.

Tests the job logging utilities including JobLogger, JobLogHandler,
and job_logging_context for concurrent job isolation.
"""
import pytest
import logging
from unittest.mock import MagicMock, patch


class TestJobLoggingContext:
    """Tests for job_logging_context context manager."""
    
    def test_job_logging_context_sets_and_resets_job_id(self):
        """Test that job_logging_context sets and resets the current job ID."""
        from backend.workers.worker_logging import job_logging_context, _current_job_id
        
        # Initially no job
        assert _current_job_id.get() is None
        
        # Inside context, job is set
        with job_logging_context("job123"):
            assert _current_job_id.get() == "job123"
        
        # After context, job is reset
        assert _current_job_id.get() is None
    
    def test_job_logging_context_nested(self):
        """Test nested job_logging_context calls."""
        from backend.workers.worker_logging import job_logging_context, _current_job_id
        
        with job_logging_context("outer_job"):
            assert _current_job_id.get() == "outer_job"
            
            with job_logging_context("inner_job"):
                assert _current_job_id.get() == "inner_job"
            
            # After inner context, outer job is restored
            assert _current_job_id.get() == "outer_job"
        
        assert _current_job_id.get() is None
    
    def test_job_logging_context_handles_exception(self):
        """Test that job_logging_context resets even on exception."""
        from backend.workers.worker_logging import job_logging_context, _current_job_id
        
        try:
            with job_logging_context("job123"):
                assert _current_job_id.get() == "job123"
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Job should still be reset after exception
        assert _current_job_id.get() is None


class TestJobLogHandler:
    """Tests for JobLogHandler class."""
    
    @pytest.fixture
    def mock_job_manager(self):
        """Create a mock JobManager."""
        manager = MagicMock()
        manager.append_worker_log.return_value = None
        return manager
    
    def test_job_log_handler_init(self, mock_job_manager):
        """Test JobLogHandler initialization."""
        from backend.workers.worker_logging import JobLogHandler
        
        handler = JobLogHandler(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        
        assert handler.job_id == "job123"
        assert handler.worker_name == "audio"
        assert handler.job_manager == mock_job_manager
        assert handler.level == logging.INFO
    
    def test_job_log_handler_custom_level(self, mock_job_manager):
        """Test JobLogHandler with custom level."""
        from backend.workers.worker_logging import JobLogHandler
        
        handler = JobLogHandler(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager,
            level=logging.DEBUG
        )
        
        assert handler.level == logging.DEBUG
    
    def test_job_log_handler_emit_logs_to_firestore(self, mock_job_manager):
        """Test that emit() calls job_manager.append_worker_log."""
        from backend.workers.worker_logging import JobLogHandler, job_logging_context
        
        handler = JobLogHandler(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Emit within the job context
        with job_logging_context("job123"):
            handler.emit(record)
        
        # Should have called append_worker_log
        mock_job_manager.append_worker_log.assert_called()
    
    def test_job_log_handler_filters_other_job_context(self, mock_job_manager):
        """Test that handler filters logs from other job contexts."""
        from backend.workers.worker_logging import JobLogHandler, job_logging_context
        
        handler = JobLogHandler(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Emit from a different job's context
        with job_logging_context("different_job"):
            handler.emit(record)
        
        # Should NOT have called append_worker_log
        mock_job_manager.append_worker_log.assert_not_called()
    
    def test_job_log_handler_deduplication(self, mock_job_manager):
        """Test that handler deduplicates repeated messages."""
        from backend.workers.worker_logging import JobLogHandler, job_logging_context
        
        handler = JobLogHandler(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Duplicate message",
            args=(),
            exc_info=None
        )
        
        with job_logging_context("job123"):
            # Emit the same record twice
            handler.emit(record)
            handler.emit(record)
        
        # Should only be called once due to deduplication
        assert mock_job_manager.append_worker_log.call_count == 1


class TestJobLogger:
    """Tests for JobLogger class."""
    
    @pytest.fixture
    def mock_job_manager(self):
        """Create a mock JobManager."""
        manager = MagicMock()
        manager.append_worker_log.return_value = None
        return manager
    
    def test_job_logger_init(self, mock_job_manager):
        """Test JobLogger initialization."""
        from backend.workers.worker_logging import JobLogger
        
        logger = JobLogger(
            job_id="job123",
            worker_name="lyrics",
            job_manager=mock_job_manager
        )
        
        assert logger.job_id == "job123"
        assert logger.worker_name == "lyrics"
        assert logger.job_manager == mock_job_manager
    
    def test_job_logger_info(self, mock_job_manager):
        """Test JobLogger.info() method."""
        from backend.workers.worker_logging import JobLogger
        
        logger = JobLogger(
            job_id="job123",
            worker_name="lyrics",
            job_manager=mock_job_manager
        )
        
        logger.info("Processing started")
        
        mock_job_manager.append_worker_log.assert_called_with(
            job_id="job123",
            worker="lyrics",
            level="INFO",
            message="Processing started"
        )
    
    def test_job_logger_warning(self, mock_job_manager):
        """Test JobLogger.warning() method."""
        from backend.workers.worker_logging import JobLogger
        
        logger = JobLogger(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        
        logger.warning("Low memory")
        
        mock_job_manager.append_worker_log.assert_called_with(
            job_id="job123",
            worker="audio",
            level="WARNING",
            message="Low memory"
        )
    
    def test_job_logger_error(self, mock_job_manager):
        """Test JobLogger.error() method."""
        from backend.workers.worker_logging import JobLogger
        
        logger = JobLogger(
            job_id="job123",
            worker_name="video",
            job_manager=mock_job_manager
        )
        
        logger.error("Processing failed")
        
        mock_job_manager.append_worker_log.assert_called_with(
            job_id="job123",
            worker="video",
            level="ERROR",
            message="Processing failed"
        )
    
    def test_job_logger_debug(self, mock_job_manager):
        """Test JobLogger.debug() method."""
        from backend.workers.worker_logging import JobLogger
        
        logger = JobLogger(
            job_id="job123",
            worker_name="screens",
            job_manager=mock_job_manager
        )
        
        logger.debug("Debug info")
        
        mock_job_manager.append_worker_log.assert_called_with(
            job_id="job123",
            worker="screens",
            level="DEBUG",
            message="Debug info"
        )
    
    def test_job_logger_with_format_args(self, mock_job_manager):
        """Test JobLogger with format arguments."""
        from backend.workers.worker_logging import JobLogger
        
        logger = JobLogger(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        
        logger.info("Processing %s of %d", "audio", 10)
        
        mock_job_manager.append_worker_log.assert_called_with(
            job_id="job123",
            worker="audio",
            level="INFO",
            message="Processing audio of 10"
        )
    
    def test_job_logger_handles_firestore_error(self, mock_job_manager):
        """Test that JobLogger handles Firestore errors gracefully."""
        from backend.workers.worker_logging import JobLogger
        
        mock_job_manager.append_worker_log.side_effect = Exception("Firestore error")
        
        logger = JobLogger(
            job_id="job123",
            worker_name="audio",
            job_manager=mock_job_manager
        )
        
        # Should not raise exception
        logger.info("Test message")


class TestCreateJobLogger:
    """Tests for create_job_logger function."""
    
    def test_create_job_logger(self):
        """Test create_job_logger creates a JobLogger."""
        from backend.workers.worker_logging import create_job_logger, JobLogger
        
        # Patch at the source module where JobManager is imported
        with patch('backend.services.job_manager.JobManager'):
            logger = create_job_logger("job123", "audio")
            
            assert isinstance(logger, JobLogger)
            assert logger.job_id == "job123"
            assert logger.worker_name == "audio"


class TestSetupJobLogging:
    """Tests for setup_job_logging function."""
    
    def test_setup_job_logging_returns_handler(self):
        """Test setup_job_logging returns a JobLogHandler."""
        from backend.workers.worker_logging import setup_job_logging, JobLogHandler
        
        # Patch at the source module
        with patch('backend.services.job_manager.JobManager'):
            handler = setup_job_logging("job123", "lyrics", "test_logger_wl1")
            
            assert isinstance(handler, JobLogHandler)
            assert handler.job_id == "job123"
            assert handler.worker_name == "lyrics"
            
            # Clean up - remove the handler
            logging.getLogger("test_logger_wl1").removeHandler(handler)
    
    def test_setup_job_logging_adds_handler_to_loggers(self):
        """Test setup_job_logging adds handler to specified loggers."""
        from backend.workers.worker_logging import setup_job_logging
        
        with patch('backend.services.job_manager.JobManager'):
            handler = setup_job_logging("job123", "audio", "test_logger_wl2", "test_logger_wl3")
            
            # Check handlers are added
            assert handler in logging.getLogger("test_logger_wl2").handlers
            assert handler in logging.getLogger("test_logger_wl3").handlers
            
            # Clean up
            logging.getLogger("test_logger_wl2").removeHandler(handler)
            logging.getLogger("test_logger_wl3").removeHandler(handler)
