import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import patch, MagicMock
import pytest


class TestTelemetry:
    def test_init_telemetry_skips_when_not_available(self):
        with patch("agents.telemetry._OTEL_AVAILABLE", False):
            from agents.telemetry import init_telemetry

            result = init_telemetry()
            assert result is None

    def test_init_telemetry_configures_when_available(self):
        with patch("agents.telemetry._OTEL_AVAILABLE", True):
            with patch("agents.telemetry.trace") as mock_trace:
                with patch("agents.telemetry.Resource") as mock_resource:
                    with patch("agents.telemetry.TracerProvider") as mock_provider:
                        from agents.telemetry import init_telemetry

                        init_telemetry()
                        mock_trace.set_tracer_provider.assert_called_once()

    def test_get_tracer_returns_noop_when_unavailable(self):
        with patch("agents.telemetry._OTEL_AVAILABLE", False):
            from agents.telemetry import get_tracer

            tracer = get_tracer()
            span = tracer.start_span("test")
            span.set_attribute("key", "value")
            span.record_exception(ValueError("test"))
            span.set_status("ok")

    def test_noop_span_context_manager(self):
        from agents.telemetry import _NoopSpan

        span = _NoopSpan()
        with span:
            pass

    def test_noop_tracer_start_as_current_span(self):
        from agents.telemetry import _NoopTracer

        tracer = _NoopTracer()
        with tracer.start_as_current_span("test"):
            pass

    def test_tracer_module_level_export(self):
        from agents.telemetry import tracer

        assert tracer is not None
