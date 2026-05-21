import json
import os
import logging
from logging.handlers import RotatingFileHandler
from insighttrail.logger import (
    JSONFormatter,
    setup_logger,
    get_logger_stats,
    should_log_success,
    logger,
    shutdown_logger,
)


class TestJSONFormatter:
    def test_json_formatter_output(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        record.trace_id = "test-trace-123"
        record.request_method = "GET"
        record.request_path = "/api/test"
        record.status = 200
        record.duration = 0.05
        record.client = "127.0.0.1"

        output = formatter.format(record)
        entry = json.loads(output)

        assert entry["trace_id"] == "test-trace-123"
        assert entry["level"] == "INFO"
        assert entry["request"]["method"] == "GET"
        assert entry["request"]["path"] == "/api/test"
        assert entry["request"]["status"] == 200
        assert entry["request"]["duration_ms"] == 50.0
        assert entry["request"]["client"] == "127.0.0.1"

    def test_error_log_contains_traceback(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=None,
            exc_info=None,
        )
        record.trace_id = "error-trace"
        record.error = "Something went wrong"
        record.error_type = "RuntimeError"
        record.traceback = "Traceback (most recent call last):\n  File \"test.py\", line 1\nRuntimeError: Something went wrong"

        output = formatter.format(record)
        entry = json.loads(output)

        assert entry["error"]["type"] == "RuntimeError"
        assert entry["error"]["message"] == "Something went wrong"
        assert "Traceback" in entry["error"]["traceback"]


class TestSetupLogger:
    def test_log_directory_created(self, tmp_path):
        log_file = str(tmp_path / "subdir" / "nested" / "test.log")
        setup_logger(log_file, "INFO", 1024 * 1024, 5, async_logging=False)
        assert os.path.exists(log_file) or os.path.exists(os.path.dirname(log_file))

    def test_async_logging_enabled(self, tmp_path):
        log_file = str(tmp_path / "async_test.log")
        setup_logger(log_file, "INFO", 1024 * 1024, 5, async_logging=True, log_queue_size=100)
        stats = get_logger_stats()
        assert stats["async_logging_enabled"] is True

    def test_sync_logging_fallback(self, tmp_path):
        log_file = str(tmp_path / "sync_test.log")
        setup_logger(log_file, "INFO", 1024 * 1024, 5, async_logging=False)
        stats = get_logger_stats()
        assert stats["async_logging_enabled"] is False

    def test_log_file_rotation(self, tmp_path):
        log_file = str(tmp_path / "rotate_test.log")
        small_size = 100
        setup_logger(log_file, "DEBUG", small_size, 3, async_logging=False)

        for i in range(20):
            logger.info(f"Log message {i}", extra={
                "trace_id": f"trace-{i}",
                "request_method": "GET",
                "request_path": f"/test/{i}",
                "status": 200,
                "duration": 0.01,
                "client": "127.0.0.1",
            })

        log_dir = os.path.dirname(log_file)
        log_files = [f for f in os.listdir(log_dir) if f.startswith("rotate_test.log")]
        assert len(log_files) > 1


class TestShouldLogSuccess:
    def test_should_log_success_rate_1(self):
        assert should_log_success(0.01, success_log_sample_rate=1.0) is True

    def test_should_log_success_rate_0(self):
        assert should_log_success(0.01, success_log_sample_rate=0.0) is False

    def test_should_log_slow_request(self):
        assert should_log_success(
            0.5,
            success_log_sample_rate=0.0,
            slow_request_threshold_ms=100,
        ) is True

    def test_should_log_fast_request_with_zero_rate(self):
        assert should_log_success(
            0.001,
            success_log_sample_rate=0.0,
            slow_request_threshold_ms=100,
        ) is False


class TestLoggerStats:
    def test_get_logger_stats(self, tmp_path):
        log_file = str(tmp_path / "stats_test.log")
        setup_logger(log_file, "INFO", 1024 * 1024, 5, async_logging=True)
        stats = get_logger_stats()
        assert "queue_depth" in stats
        assert "dropped_log_count" in stats
        assert "async_logging_enabled" in stats
        assert isinstance(stats["queue_depth"], int)
        assert isinstance(stats["dropped_log_count"], int)
        assert isinstance(stats["async_logging_enabled"], bool)
