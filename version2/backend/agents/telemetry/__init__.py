"""
OpenTelemetry initialization for the agent system.

Exports:
- init_telemetry(): call once at startup to configure the global tracer
- tracer: the module-level OpenTelemetry tracer instance
- AgentSpan: async context manager that wraps a function body in a span

Usage:
    from agents.telemetry import tracer, AgentSpan

    async with AgentSpan("agent.run", {"query": query[:50]}):
        ...
"""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore
    TracerProvider = None  # type: ignore
    Resource = None  # type: ignore
    SERVICE_NAME = "service.name"
    BatchSpanProcessor = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    logger.info("OpenTelemetry not available — tracing disabled")


def init_telemetry() -> None:
    if not _OTEL_AVAILABLE:
        logger.info("OpenTelemetry skipped (imports unavailable)")
        return

    resource = Resource.create({SERVICE_NAME: "datasage-agents"})
    provider = TracerProvider(resource=resource)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info("OpenTelemetry OTLP exporter configured: %s", endpoint)
        except Exception as e:
            logger.warning("OpenTelemetry exporter init failed: %s", e)

    trace.set_tracer_provider(provider)  # type: ignore[union-attr]
    logger.info("OpenTelemetry tracer initialized")


def get_tracer() -> "trace.Tracer":
    if _OTEL_AVAILABLE:
        return trace.get_tracer(__name__)
    return _NoopTracer()  # type: ignore


class _NoopTracer:
    """Fallback tracer when OpenTelemetry is not installed."""

    def start_span(self, name, attributes=None, **kwargs):
        return _NoopSpan()

    def start_as_current_span(self, name, attributes=None, **kwargs):
        return _NoopSpan()

    @property
    def tracer(self):
        return self


class _NoopSpan:
    """No-op span context manager."""

    def set_attribute(self, key, value):
        pass

    def record_exception(self, exc):
        pass

    def set_status(self, status):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


tracer = get_tracer()
