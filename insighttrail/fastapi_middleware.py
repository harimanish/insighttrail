import os
import time

from starlette.middleware.base import BaseHTTPMiddleware

from ._core import load_required_packages
from .logger import log_error, log_request, setup_logger
from .metrics import get_metrics, record_metrics
from .traces import generate_trace_id


class FastAPIInsightTrailMiddleware:
    def __init__(
        self,
        app,
        log_file="insighttrail.log",
        log_level="info",
        max_file_size=10485760,
        backup_count=5,
        enable_ui=True,
        url_prefix="/insight",
    ):
        try:
            from fastapi import FastAPI
            from fastapi.templating import Jinja2Templates

            self._FastAPI = FastAPI
            self._Jinja2Templates = Jinja2Templates
        except ImportError:
            raise ImportError(
                "FastAPIInsightTrailMiddleware requires FastAPI. "
                "Install it with: pip install insighttrail[fastapi]"
            )

        self.app = app
        self._fastapi_app = None
        root_path = app.root_path if hasattr(app, "root_path") else os.getcwd()
        self.required_packages = load_required_packages(root_path)
        self._url_prefix = url_prefix

        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self._templates = self._Jinja2Templates(directory=template_dir)

        setup_logger(log_file, log_level, max_file_size, backup_count)
        self.log_file = log_file

        self._add_middleware()

        if enable_ui:
            self._setup_ui(url_prefix)

    def _add_middleware(self):
        class InsightTrailMiddlewareClass(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                generate_trace_id()
                start_time = time.time()

                try:
                    response = await call_next(request)
                    duration = time.time() - start_time
                    status = str(response.status_code)
                    record_metrics(request.method, status, duration)
                    client = request.client.host if request.client else "unknown"
                    log_request(
                        request.method,
                        request.url.path,
                        response.status_code,
                        duration,
                        client,
                    )
                    return response
                except Exception as e:
                    duration = time.time() - start_time
                    client = request.client.host if request.client else "unknown"
                    log_error(request.method, request.url.path, duration, client, e)
                    raise

        self.app.add_middleware(InsightTrailMiddlewareClass)

    def _setup_ui(self, url_prefix):
        from ._core import get_package_info as _get_pkg_info
        from ._core import parse_log_file as _parse_log

        log_file = self.log_file
        required_packages = self.required_packages
        templates = self._templates

        from fastapi import APIRouter
        from fastapi.requests import Request
        from fastapi.responses import HTMLResponse, JSONResponse

        router = APIRouter(prefix=url_prefix, tags=["InsightTrail"])

        @router.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={"url_prefix": url_prefix},
            )

        @router.get("/api/packages")
        async def get_packages():
            return JSONResponse(_get_pkg_info(required_packages))

        @router.get("/api/logs")
        async def get_logs():
            return JSONResponse(_parse_log(log_file))

        @router.get("/api/analytics/logs")
        async def fetch_logs():
            return JSONResponse({"logs": _parse_log(log_file), "metrics": get_metrics()})

        @router.get("/api/analytics/search")
        async def search_by_trace_id(trace_id: str):
            logs = _parse_log(log_file)
            result = [log for log in logs if log.get("trace_id") == trace_id]
            return JSONResponse({"logs": result, "metrics": get_metrics()})

        self.app.include_router(router)
