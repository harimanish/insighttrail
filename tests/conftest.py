import os
import json
import pytest
from flask import Flask
from fastapi import FastAPI
from fastapi.testclient import TestClient
from insighttrail import FlaskInsightTrail, FastAPIInsightTrail
from insighttrail.logger import shutdown_logger, logger


@pytest.fixture(autouse=True)
def reset_logger():
    shutdown_logger()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    yield
    shutdown_logger()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)


@pytest.fixture
def tmp_log_dir(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def log_file(tmp_log_dir):
    return str(tmp_log_dir / "insighttrail.log")


@pytest.fixture
def flask_app(log_file):
    app = Flask(__name__)

    @app.route("/")
    def home():
        return {"message": "Hello"}

    @app.route("/error")
    def error():
        raise ValueError("Test error")

    @app.route("/slow")
    def slow():
        import time
        time.sleep(0.1)
        return {"status": "slow"}

    mw = FlaskInsightTrail(
        app,
        log_file=log_file,
        log_level="DEBUG",
        enable_ui=True,
        url_prefix="/insight",
        track_internal_requests=False,
        async_logging=False,
        dependency_check=False,
        enable_excel_reports=True,
    )
    app.insighttrail_middleware = mw
    return app


@pytest.fixture
def flask_client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def fastapi_app(log_file):
    app = FastAPI()

    @app.get("/")
    def home():
        return {"message": "Hello"}

    @app.get("/error")
    def error():
        raise ValueError("Test error")

    @app.get("/slow")
    def slow():
        import time
        time.sleep(0.1)
        return {"status": "slow"}

    mw = FastAPIInsightTrail(
        app,
        log_file=log_file,
        log_level="DEBUG",
        enable_ui=True,
        url_prefix="/insight",
        track_internal_requests=False,
        async_logging=False,
        dependency_check=False,
        enable_excel_reports=True,
    )
    app.insighttrail_middleware = mw
    return app


@pytest.fixture
def fastapi_client(fastapi_app):
    return TestClient(fastapi_app, raise_server_exceptions=False)
