import pytest
from flask import Flask
from fastapi import FastAPI
from fastapi.testclient import TestClient
from insighttrail import InsightTrail, FlaskInsightTrail, FastAPIInsightTrail


class TestInsightTrail:
    def test_detects_flask(self, tmp_path):
        log_file = str(tmp_path / "logs" / "test.log")
        app = Flask(__name__)
        wrapper = InsightTrail(app, log_file=log_file, enable_ui=False, async_logging=False)
        assert wrapper.framework == "flask"

    def test_detects_fastapi(self, tmp_path):
        log_file = str(tmp_path / "logs" / "test.log")
        app = FastAPI()
        wrapper = InsightTrail(app, log_file=log_file, enable_ui=False, async_logging=False)
        assert wrapper.framework == "fastapi"

    def test_rejects_unknown_framework(self):
        class UnknownApp:
            pass

        app = UnknownApp()
        with pytest.raises(TypeError) as exc_info:
            InsightTrail(app)
        assert "Unsupported app type" in str(exc_info.value)

    def test_flask_delegates_to_middleware(self, tmp_path):
        log_file = str(tmp_path / "logs" / "test.log")
        app = Flask(__name__)
        wrapper = InsightTrail(app, log_file=log_file, enable_ui=False, async_logging=False)
        assert isinstance(wrapper._impl, FlaskInsightTrail)

    def test_fastapi_delegates_to_adapter(self, tmp_path):
        log_file = str(tmp_path / "logs" / "test.log")
        app = FastAPI()
        wrapper = InsightTrail(app, log_file=log_file, enable_ui=False, async_logging=False)
        assert isinstance(wrapper._impl, FastAPIInsightTrail)

    def test_flask_request_handling(self, tmp_path):
        log_file = str(tmp_path / "logs" / "test.log")
        app = Flask(__name__)

        @app.route("/test")
        def test_route():
            return {"status": "ok"}

        wrapper = InsightTrail(
            app,
            log_file=log_file,
            enable_ui=True,
            async_logging=False,
        )
        client = app.test_client()
        resp = client.get("/test")
        assert resp.status_code == 200
        resp = client.get("/insight/")
        assert resp.status_code == 200

    def test_fastapi_request_handling(self, tmp_path):
        log_file = str(tmp_path / "logs" / "test.log")
        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        wrapper = InsightTrail(
            app,
            log_file=log_file,
            enable_ui=True,
            async_logging=False,
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 200
        resp = client.get("/insight/")
        assert resp.status_code == 200
