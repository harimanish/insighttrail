import contextvars
import uuid

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "insighttrail_trace_id", default=""
)


def generate_trace_id():
    trace_id = str(uuid.uuid4())
    _trace_id_var.set(trace_id)
    return trace_id


def get_trace_id():
    return _trace_id_var.get() or "N/A"


def set_trace_id(trace_id):
    _trace_id_var.set(trace_id)
