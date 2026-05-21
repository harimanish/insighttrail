from .middleware import InsightTrailMiddleware
from .fastapi_adapter import FastAPIInsightTrail


class InsightTrail:
    def __init__(self, app, **kwargs):
        app_module = app.__class__.__module__
        app_name = app.__class__.__name__

        if app_module.startswith('flask'):
            self._impl = InsightTrailMiddleware(app, **kwargs)
            self.framework = 'flask'
            return

        if app_module.startswith('fastapi') or app_name == 'FastAPI':
            self._impl = FastAPIInsightTrail(app, **kwargs)
            self.framework = 'fastapi'
            return

        raise TypeError(
            f'Unsupported app type: {app.__class__.__module__}.{app.__class__.__name__}. '
            'Supported frameworks: Flask and FastAPI.'
        )


__all__ = ['InsightTrail', 'InsightTrailMiddleware', 'FastAPIInsightTrail']
