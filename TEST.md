# Testing

## Setup

Install dev dependencies:

```bash
uv sync --group dev
```

## Run Tests

Run all tests:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=insighttrail --cov-report=term-missing
```

Run a specific test file:

```bash
uv run pytest tests/test_middleware.py
```

Run a single test:

```bash
uv run pytest tests/test_middleware.py::TestRequestLogging::test_successful_request_logged
```

Run tests matching a keyword:

```bash
uv run pytest -k "excel"
```

## Test Structure

| File | Coverage |
|------|----------|
| `test_middleware.py` | Flask middleware: init, request logging, dashboard UI, Excel reports |
| `test_fastapi_adapter.py` | FastAPI adapter: init, request logging, dashboard, Excel reports |
| `test_logger.py` | JSON formatter, async/sync logging, log rotation, sampling |
| `test_metrics.py` | Metrics recording, uptime, process info, system metrics |
| `test_insighttrail.py` | Unified wrapper: framework detection, delegation |

## Fixtures

Shared fixtures in `conftest.py`:

- `flask_app` — Flask app with middleware attached
- `flask_client` — Flask test client
- `fastapi_app` — FastAPI app with middleware attached
- `fastapi_client` — FastAPI test client (httpx)
- `log_file` — Temp log file path (auto-cleaned)
- `tmp_log_dir` — Temp log directory (auto-cleaned)

Each test gets an isolated temp directory. The global logger is reset between tests.
