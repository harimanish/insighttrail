def test_fastapi_import():
    from insighttrail import FastAPIInsightTrail

    assert FastAPIInsightTrail is not None


def test_fastapi_init_no_ui():
    from fastapi import FastAPI

    from insighttrail import FastAPIInsightTrail

    app = FastAPI()
    middleware = FastAPIInsightTrail(app, enable_ui=False)

    @app.get("/")
    def home():
        return {"hello": "world"}

    assert middleware is not None
    assert middleware.required_packages is not None


def test_fastapi_init_with_ui():
    from fastapi import FastAPI

    from insighttrail import FastAPIInsightTrail

    app = FastAPI()
    middleware = FastAPIInsightTrail(app, enable_ui=True, url_prefix="/insight")

    @app.get("/")
    def home():
        return {"hello": "world"}

    assert middleware is not None
    assert middleware.url_prefix == "/insight"


def test_fastapi_custom_url_prefix():
    from fastapi import FastAPI

    from insighttrail import FastAPIInsightTrail

    app = FastAPI()
    middleware = FastAPIInsightTrail(app, url_prefix="/custom")

    @app.get("/")
    def home():
        return {"hello": "world"}

    assert middleware.url_prefix == "/custom"


def test_fastapi_api_endpoints():
    import os
    import tempfile
    import uuid

    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from insighttrail import FastAPIInsightTrail

    log_file = os.path.join(tempfile.gettempdir(), f"test_insighttrail_{uuid.uuid4()}.log")

    try:
        app = FastAPI()
        FastAPIInsightTrail(app, log_file=log_file, url_prefix="/insight")

        @app.get("/")
        def home():
            return {"hello": "world"}

        client = TestClient(app)

        response = client.get("/insight/api/packages")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

        response = client.get("/insight/api/analytics/logs")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "metrics" in data

        response = client.get("/")
        assert response.status_code == 200

        response = client.get("/insight/")
        assert response.status_code == 200
        assert "InsightTrail" in response.text

        trace_id = str(uuid.uuid4())
        response = client.get(f"/insight/api/analytics/search?trace_id={trace_id}")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "metrics" in data
    finally:
        if os.path.exists(log_file):
            os.remove(log_file)


def test_fastapi_middleware_records_metrics():
    import os
    import tempfile
    import uuid

    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from insighttrail import FastAPIInsightTrail
    from insighttrail.metrics import METRICS_STORE, get_metrics

    METRICS_STORE.clear()

    log_file = os.path.join(tempfile.gettempdir(), f"test_metrics_{uuid.uuid4()}.log")

    try:
        app = FastAPI()
        FastAPIInsightTrail(app, log_file=log_file, enable_ui=False)

        @app.get("/")
        def home():
            return {"hello": "world"}

        client = TestClient(app)
        client.get("/")
        client.get("/")
        client.get("/")

        metrics = get_metrics()
        assert metrics["total_requests"] == 3
    finally:
        if os.path.exists(log_file):
            os.remove(log_file)
