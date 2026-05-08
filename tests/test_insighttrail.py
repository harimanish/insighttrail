from importlib.metadata import version

from flask import Flask


def test_version():
    pkg_version = version("insighttrail")
    assert pkg_version == "0.1.0"


def test_import():
    from insighttrail import InsightTrailMiddleware, __version__

    assert __version__ == "0.1.0"
    assert InsightTrailMiddleware is not None


def test_no_requirements_txt_found(tmp_path):
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    app.root_path = str(tmp_path)

    InsightTrailMiddleware(app, enable_ui=False)


def test_requirements_txt_in_dir(tmp_path):
    from insighttrail import InsightTrailMiddleware

    req = tmp_path / "requirements.txt"
    req.write_text("flask\nrequests\n# comment\npsutil==5.0\n")

    app = Flask(__name__)
    app.root_path = str(tmp_path)

    middleware = InsightTrailMiddleware(app, enable_ui=False)
    assert "flask" in middleware.required_packages
    assert "requests" in middleware.required_packages
    assert "psutil" in middleware.required_packages


def test_requirements_txt_parent_dir(tmp_path):
    from insighttrail import InsightTrailMiddleware

    req = tmp_path / "requirements.txt"
    req.write_text("django\n")

    subdir = tmp_path / "subdir" / "app"
    subdir.mkdir(parents=True)

    app = Flask(__name__)
    app.root_path = str(subdir)

    middleware = InsightTrailMiddleware(app, enable_ui=False)
    assert "django" in middleware.required_packages


def test_ui_enabled_registers_blueprint():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    InsightTrailMiddleware(app, enable_ui=True)

    rule_endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "insighttrail.index" in rule_endpoints
    assert "insighttrail.get_packages" in rule_endpoints


def test_ui_disabled_no_blueprint():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    InsightTrailMiddleware(app, enable_ui=False)

    rule_endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "insighttrail.index" not in rule_endpoints


def test_custom_url_prefix():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    InsightTrailMiddleware(app, enable_ui=True, url_prefix="/monitor")

    rule_endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "insighttrail.index" in rule_endpoints
    paths = [rule.rule for rule in app.url_map.iter_rules()]
    assert any(p.startswith("/monitor") for p in paths)


def test_package_info_includes_insighttrail():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    middleware = InsightTrailMiddleware(app, enable_ui=False)

    info = middleware._get_package_info()
    names = [p["name"] for p in info]
    assert "insighttrail" in names


def test_wsgi_call_returns_response():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)

    @app.route("/")
    def index():
        return "ok"

    InsightTrailMiddleware(app, enable_ui=False)

    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"ok" in resp.data


def test_middleware_url_prefix_root():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    InsightTrailMiddleware(app, enable_ui=True, url_prefix="/insight")

    with app.test_client() as client:
        resp = client.get("/insight/")
        assert resp.status_code == 200


def test_middleware_logs_api():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    InsightTrailMiddleware(app, enable_ui=True, url_prefix="/insight")

    with app.test_client() as client:
        resp = client.get("/insight/api/logs")
        assert resp.status_code == 200
        assert resp.is_json


def test_middleware_packages_api():
    from insighttrail import InsightTrailMiddleware

    app = Flask(__name__)
    InsightTrailMiddleware(app, enable_ui=True, url_prefix="/insight")

    with app.test_client() as client:
        resp = client.get("/insight/api/packages")
        assert resp.status_code == 200
        assert resp.is_json
        packages = resp.get_json()
        assert isinstance(packages, list)
