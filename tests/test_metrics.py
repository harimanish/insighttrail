import time
from insighttrail.metrics import (
    METRICS_STORE,
    PROCESS_START_TIMES,
    RESTART_COUNT,
    record_metrics,
    get_metrics,
)


class MockRequest:
    def __init__(self, method="GET"):
        self.method = method


class MockResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def reset_metrics():
    METRICS_STORE.clear()
    PROCESS_START_TIMES.clear()


class TestRecordMetrics:
    def setup_method(self):
        reset_metrics()

    def test_record_metrics_increments(self):
        req = MockRequest()
        resp = MockResponse()
        record_metrics(req, resp, 0.05)
        assert METRICS_STORE["total_requests"] == 1
        record_metrics(req, resp, 0.03)
        assert METRICS_STORE["total_requests"] == 2

    def test_record_metrics_method_count(self):
        req = MockRequest(method="GET")
        resp = MockResponse()
        record_metrics(req, resp, 0.05)
        assert METRICS_STORE["GET_requests"] == 1

        req_post = MockRequest(method="POST")
        record_metrics(req_post, resp, 0.05)
        assert METRICS_STORE["POST_requests"] == 1

    def test_record_metrics_status_count(self):
        req = MockRequest()
        resp = MockResponse(status_code=200)
        record_metrics(req, resp, 0.05)
        assert METRICS_STORE["status_200"] == 1

        resp_404 = MockResponse(status_code=404)
        record_metrics(req, resp_404, 0.05)
        assert METRICS_STORE["status_404"] == 1

    def test_record_metrics_duration(self):
        req = MockRequest()
        resp = MockResponse()
        record_metrics(req, resp, 0.05)
        record_metrics(req, resp, 0.10)
        assert abs(METRICS_STORE["total_duration"] - 0.15) < 0.0001


class TestGetMetrics:
    def setup_method(self):
        reset_metrics()

    def test_get_metrics_returns_uptime(self):
        metrics = get_metrics()
        assert "uptime_seconds" in metrics
        assert metrics["uptime_seconds"] > 0

    def test_get_metrics_returns_process_info(self):
        metrics = get_metrics()
        assert "process_info" in metrics
        info = metrics["process_info"]
        assert "main_pid" in info
        assert "cpu_cores" in info
        assert "worker_count" in info

    def test_get_metrics_returns_system_metrics(self):
        metrics = get_metrics()
        assert "system_metrics" in metrics
        sys = metrics["system_metrics"]
        assert "cpu_percent" in sys
        assert "memory_percent" in sys
        assert "disk_usage" in sys

    def test_get_metrics_includes_stored_metrics(self):
        req = MockRequest()
        resp = MockResponse()
        record_metrics(req, resp, 0.05)
        metrics = get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["total_duration"] == 0.05
