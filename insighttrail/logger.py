import logging
import queue
import random
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import traceback
import os
import json
import datetime
import psutil
import sys
import threading
import platform
import atexit

# Configure the logger
logger = logging.getLogger('insighttrail')
_listener = None
_log_queue = None
_dropped_log_count = 0


class NonBlockingQueueHandler(QueueHandler):
    def enqueue(self, record):
        global _dropped_log_count
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            _dropped_log_count += 1

class JSONFormatter(logging.Formatter):
    def format(self, record):
        # Get basic request info
        log_entry = {
            "trace_id": getattr(record, "trace_id", None),
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "request": {
                "method": getattr(record, "request_method", None),
                "path": getattr(record, "request_path", None),
                "status": getattr(record, "status", None),
                "duration_ms": getattr(record, "duration", 0) * 1000 if getattr(record, "duration", None) else None,
                "client": getattr(record, "client", None)
            }
        }

        # Add error information if present
        error = getattr(record, "error", None)
        if error:
            log_entry["error"] = {
                "type": getattr(record, "error_type", None),
                "message": error,
                "traceback": getattr(record, "traceback", None)
            }

        # Add runtime metrics if present
        runtime_info = getattr(record, "runtime_info", None)
        if runtime_info:
            log_entry["runtime"] = {
                "python": {
                    "version": runtime_info.get("python", {}).get("version"),
                    "implementation": runtime_info.get("python", {}).get("implementation"),
                    "thread_count": runtime_info.get("python", {}).get("thread_count")
                },
                "process": {
                    "pid": runtime_info.get("process", {}).get("pid"),
                    "memory_mb": runtime_info.get("process", {}).get("memory_info", {}).get("rss", 0) / (1024 * 1024),
                    "cpu_percent": runtime_info.get("process", {}).get("cpu_percent")
                },
                "env_vars": runtime_info.get("environment", {}).get("vars", {})
            }

        # Add system metrics if present
        system_metrics = getattr(record, "system_metrics", None)
        if system_metrics:
            log_entry["system"] = {
                "cpu": {
                    "percent": system_metrics.get("cpu", {}).get("percent"),
                    "count": system_metrics.get("cpu", {}).get("count")
                },
                "memory": {
                    "percent": system_metrics.get("memory", {}).get("percent"),
                    "available_gb": system_metrics.get("memory", {}).get("available", 0) / (1024 * 1024 * 1024)
                },
                "disk": {
                    "percent": system_metrics.get("disk", {}).get("percent"),
                    "free_gb": system_metrics.get("disk", {}).get("free", 0) / (1024 * 1024 * 1024)
                }
            }

        return json.dumps(log_entry)

def shutdown_logger():
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def setup_logger(log_file, log_level_str, max_file_size, backup_count,
                 async_logging=True, log_queue_size=5000):
    global _listener, _log_queue
    log_directory = os.path.dirname(log_file)
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # Map log level string to logging constant
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    rotating_handler = RotatingFileHandler(log_file, maxBytes=max_file_size, backupCount=backup_count)
    rotating_handler.setLevel(log_level)
    rotating_handler.setFormatter(JSONFormatter())

    logger.setLevel(log_level)
    logger.propagate = False

    for existing_handler in list(logger.handlers):
        logger.removeHandler(existing_handler)

    if _listener is not None:
        _listener.stop()
        _listener = None

    if async_logging:
        _log_queue = queue.Queue(maxsize=max(100, int(log_queue_size)))
        queue_handler = NonBlockingQueueHandler(_log_queue)
        queue_handler.setLevel(log_level)
        logger.addHandler(queue_handler)
        _listener = QueueListener(_log_queue, rotating_handler, respect_handler_level=True)
        _listener.start()
        atexit.register(shutdown_logger)
    else:
        logger.addHandler(rotating_handler)


def get_logger_stats():
    queue_depth = 0
    if _log_queue is not None:
        queue_depth = _log_queue.qsize()
    return {
        "queue_depth": queue_depth,
        "dropped_log_count": _dropped_log_count,
        "async_logging_enabled": _listener is not None,
    }


def should_log_success(duration_seconds, success_log_sample_rate=1.0, slow_request_threshold_ms=None):
    if slow_request_threshold_ms is not None:
        duration_ms = duration_seconds * 1000.0
        if duration_ms >= float(slow_request_threshold_ms):
            return True

    rate = float(success_log_sample_rate)
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return random.random() < rate

def get_system_metrics():
    """Get essential system metrics."""
    try:
        process = psutil.Process()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu": {
                "percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent
            },
            "process": {
                "memory_info": process.memory_info()._asdict(),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads()
            }
        }
    except Exception as e:
        return {"error": str(e)}

def get_runtime_info(capture_env_vars=False, env_allowlist=None):
    """Get essential runtime information."""
    try:
        process = psutil.Process()
        
        safe_env = {}
        if capture_env_vars:
            if env_allowlist:
                safe_env = {k: os.environ.get(k, '') for k in env_allowlist if k in os.environ}
            else:
                safe_env = {k: v for k, v in os.environ.items()
                            if not any(sensitive in k.lower()
                                      for sensitive in ['key', 'token', 'secret', 'pass', 'auth'])}

        runtime_info = {
            "python": {
                "version": sys.version.split()[0],  # Just the version number
                "implementation": platform.python_implementation(),
                "thread_count": threading.active_count()
            },
            "process": {
                "pid": process.pid,
                "memory_info": process.memory_info()._asdict(),
                "cpu_percent": process.cpu_percent(),
                "create_time": datetime.datetime.fromtimestamp(process.create_time()).isoformat()
            },
            "environment": {
                "vars": safe_env
            }
        }
        
        return runtime_info
    except Exception as e:
        return {"error": str(e)}

def log_request(request, response, duration, capture_runtime=False, capture_system_metrics=False,
                capture_env_vars=False, env_allowlist=None):
    from flask import g
    trace_id = getattr(g, 'trace_id', 'N/A')
    system_metrics = get_system_metrics() if capture_system_metrics else None
    runtime_info = get_runtime_info(capture_env_vars=capture_env_vars, env_allowlist=env_allowlist) if capture_runtime else None

    logger.info("Request completed", extra={
        "trace_id": trace_id,
        "request_method": request.method,
        "request_path": request.path,
        "status": response.status_code,
        "duration": duration,
        "client": request.remote_addr,
        "system_metrics": system_metrics,
        "runtime_info": runtime_info
    })

def log_error(request, exception, duration, capture_runtime=False, capture_system_metrics=False,
              capture_env_vars=False, env_allowlist=None):
    from flask import g
    trace_id = getattr(g, 'trace_id', 'N/A')
    error_type = exception.__class__.__name__
    status_code = 500
    
    system_metrics = get_system_metrics() if capture_system_metrics else None
    runtime_info = get_runtime_info(capture_env_vars=capture_env_vars, env_allowlist=env_allowlist) if capture_runtime else None

    # Get the full traceback
    tb = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    logger.error("Request failed", extra={
        "trace_id": trace_id,
        "request_method": request.method,
        "request_path": request.path,
        "status": status_code,
        "duration": duration,
        "client": request.remote_addr,
        "error": str(exception),
        "error_type": error_type,
        "traceback": tb,  # Use the full traceback
        "system_metrics": system_metrics,
        "runtime_info": runtime_info
    })
