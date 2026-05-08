import json
import os
import time
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, render_template, request
from werkzeug.wrappers import Request

from ._core import (
    build_error_info,
    get_package_info,
    load_required_packages,
    parse_log_file,
)
from .logger import log_error, log_request, setup_logger
from .metrics import get_metrics, record_metrics
from .traces import trace_request


class InsightTrailMiddleware:
    def __init__(
        self,
        app,
        log_file=None,
        log_level="INFO",
        max_file_size=1 * 1024 * 1024,
        backup_count=5,
        enable_ui=True,
        url_prefix="/insight",
    ):
        """
        Initialize InsightTrail middleware.

        Args:
            app: Flask application instance
            log_file: Path to log file. Defaults to 'insighttrail.log' in the
                parent directory of the app's root path.
            log_level: The logging level to use, e.g., 'INFO', 'DEBUG'.
            max_file_size: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            enable_ui: Whether to enable the web UI (default: True)
            url_prefix: URL prefix for InsightTrail routes (default: /insight)
        """
        self.app = app
        self.required_packages = load_required_packages(app.root_path)

        if log_file is None:
            # Default to a 'logs' directory in the parent of the app's root path
            app_parent_dir = os.path.dirname(app.root_path)
            log_file = os.path.join(app_parent_dir, "logs", "insighttrail.log")

        setup_logger(log_file, log_level, max_file_size, backup_count)
        self.log_file = log_file
        self._init_app(app)

        if enable_ui:
            self._setup_ui(url_prefix)

    def _get_package_info(self):
        return get_package_info(self.required_packages)

    def _init_app(self, app):
        @app.before_request
        def before_request():
            g.start_time = time.time()
            trace_request(request)

        @app.after_request
        def after_request(response):
            duration = time.time() - g.start_time
            record_metrics(request, response, duration)
            log_request(request, response, duration)
            return response

        @app.teardown_request
        def teardown_request(exception=None):
            if exception is not None:
                duration = time.time() - g.start_time
                log_error(request, exception, duration)

    def _parse_log_file(self):
        return parse_log_file(self.log_file)

    def _setup_ui(self, url_prefix):
        # Create a blueprint for InsightTrail UI
        insight_bp = Blueprint(
            "insighttrail",
            __name__,
            template_folder="templates",
            static_folder="static",
            url_prefix=url_prefix,
        )

        @insight_bp.route("/")
        def index():
            return render_template("index.html")

        @insight_bp.route("/api/packages")
        def get_packages():
            return jsonify(self._get_package_info())

        @insight_bp.route("/api/logs")
        def get_logs():
            try:
                # Return all logs in JSON format
                logs = self._parse_log_file()
                return jsonify(logs)
            except Exception as e:
                print(f"Error in get_logs: {e}")
                return jsonify({"error": str(e)}), 500

        @insight_bp.route("/api/analytics/logs", methods=["GET"])
        def fetch_logs():
            try:
                logs = self._parse_log_file()
                metrics = get_metrics()
                return jsonify({"logs": logs, "metrics": metrics})
            except Exception as e:
                print(f"Error in fetch_logs: {e}")
                return jsonify({"error": str(e)}), 500

        @insight_bp.route("/api/analytics/search", methods=["GET"])
        def search_by_trace_id():
            try:
                trace_id = request.args.get("trace_id")
                logs = self._parse_log_file()
                result = [log for log in logs if log.get("trace_id") == trace_id]
                metrics = get_metrics()
                return jsonify({"logs": result, "metrics": metrics})
            except Exception as e:
                print(f"Error in search_by_trace_id: {e}")
                return jsonify({"error": str(e)}), 500

        # Register the blueprint with the main app
        self.app.register_blueprint(insight_bp)

    def _log_error(self, error, request=None):
        request_info = None
        if request:
            request_info = {
                "url": request.path,
                "method": request.method,
                "headers": dict(request.headers),
                "params": dict(request.args),
            }
        return build_error_info(error, request_info)

    def __call__(self, environ, start_response):
        """WSGI middleware entry point."""
        request = Request(environ)
        start_time = time.time()

        try:
            response = self.app(environ, start_response)
            status_code = int(response[0].decode().split()[0])

            # Process response and gather metrics
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": getattr(g, "trace_id", str(uuid.uuid4())),
                "request": {
                    "method": request.method,
                    "path": request.path,
                    "client": request.remote_addr,
                    "user_agent": request.user_agent.string,
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "query_params": dict(request.args),
                },
                "runtime": self._get_runtime_info(),
                "system": self._get_system_metrics(),
            }

            # Only add error info for error status codes
            if status_code >= 400:
                log_entry["error"] = self._log_error(Exception(f"HTTP {status_code}"), request)

            self._write_log(log_entry)
            return response

        except Exception as e:
            # Handle uncaught exceptions
            error_info = self._log_error(e, request)

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": getattr(g, "trace_id", str(uuid.uuid4())),
                "request": {
                    "method": request.method,
                    "path": request.path,
                    "client": request.remote_addr,
                    "user_agent": request.user_agent.string,
                    "status": 500,
                    "duration_ms": (time.time() - start_time) * 1000,
                    "query_params": dict(request.args),
                },
                "runtime": self._get_runtime_info(),
                "system": self._get_system_metrics(),
                "error": error_info,
            }

            self._write_log(log_entry)

            # Return a 500 error response
            response_body = json.dumps(
                {"error": "Internal Server Error", "message": str(e)}
            ).encode("utf-8")

            response_headers = [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body))),
            ]

            start_response("500 Internal Server Error", response_headers)
            return [response_body]
