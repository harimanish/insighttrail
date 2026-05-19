# insighttrail/__init__.py

__version__ = "0.1.0"

from .middleware import InsightTrailMiddleware


def __getattr__(name):
    if name == "FastAPIInsightTrail":
        from .fastapi_adapter import FastAPIInsightTrail

        return FastAPIInsightTrail
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["InsightTrailMiddleware", "FastAPIInsightTrail"]
