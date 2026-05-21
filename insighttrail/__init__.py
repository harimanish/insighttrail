class InsightTrail:
    def __init__(self, app, **kwargs):
        app_module = app.__class__.__module__
        app_name = app.__class__.__name__

        if app_module.startswith('flask'):
            from .middleware import FlaskInsightTrail
            self._impl = FlaskInsightTrail(app, **kwargs)
            self.framework = 'flask'
            return

        if app_module.startswith('fastapi') or app_name == 'FastAPI':
            from .fastapi_adapter import FastAPIInsightTrail
            self._impl = FastAPIInsightTrail(app, **kwargs)
            self.framework = 'fastapi'
            return

        raise TypeError(
            f'Unsupported app type: {app.__class__.__module__}.{app.__class__.__name__}. '
            'Supported frameworks: Flask and FastAPI.'
        )


def __getattr__(name):
    if name == 'FlaskInsightTrail':
        from .middleware import FlaskInsightTrail
        return FlaskInsightTrail
    if name == 'FastAPIInsightTrail':
        from .fastapi_adapter import FastAPIInsightTrail
        return FastAPIInsightTrail
    raise AttributeError(f"module 'insighttrail' has no attribute '{name}'")


__all__ = ['InsightTrail', 'FlaskInsightTrail', 'FastAPIInsightTrail']
