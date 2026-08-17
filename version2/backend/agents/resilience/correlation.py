"""
Correlation ID for tracing agent runs across logs and downstream services.

Usage (automatic via BaseAgent):
    # Set at start of agent run
    set_correlation_id()

    # Retrieve anywhere in async context
    cid = get_correlation_id()

    # Propagate to downstream service calls
    headers = {"X-Correlation-ID": cid}
"""

import contextvars
import logging
import uuid

_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def generate_correlation_id() -> str:
    return uuid.uuid4().hex[:12]


def set_correlation_id(cid: str | None = None) -> str:
    value = cid or generate_correlation_id()
    _correlation_id_var.set(value)
    return value


def get_correlation_id() -> str:
    return _correlation_id_var.get()


class CorrelationFilter(logging.Filter):
    """Adds correlation_id to every log record.

    Wire into root logger at startup:
        logging.getLogger().addFilter(CorrelationFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        cid = _correlation_id_var.get("")
        record.correlation_id = cid[:8] if cid else ""
        return True
