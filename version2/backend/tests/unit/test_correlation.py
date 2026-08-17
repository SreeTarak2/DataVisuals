import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import logging
import pytest


class TestCorrelationID:
    def test_generate_correlation_id_unique(self):
        from agents.resilience.correlation import generate_correlation_id

        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_correlation_id_length(self):
        from agents.resilience.correlation import generate_correlation_id

        cid = generate_correlation_id()
        assert len(cid) == 12

    def test_set_and_get(self):
        from agents.resilience.correlation import set_correlation_id, get_correlation_id

        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"

    def test_set_generates_when_not_provided(self):
        from agents.resilience.correlation import set_correlation_id, get_correlation_id

        cid = set_correlation_id()
        assert cid
        assert get_correlation_id() == cid

    def test_get_default_empty(self):
        from agents.resilience.correlation import _correlation_id_var

        _correlation_id_var.set("")
        from agents.resilience.correlation import get_correlation_id

        assert get_correlation_id() == ""

    def test_get_default_reset(self):
        from agents.resilience.correlation import (
            set_correlation_id,
            get_correlation_id,
            _correlation_id_var,
        )

        set_correlation_id("abc")
        _correlation_id_var.set("")
        assert get_correlation_id() == ""


class TestCorrelationFilter:
    def test_filter_adds_correlation_id(self):
        from agents.resilience.correlation import CorrelationFilter, set_correlation_id

        f = CorrelationFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        set_correlation_id("abcdef123456")
        assert f.filter(record) is True
        assert record.correlation_id == "abcdef12"

    def test_filter_empty_when_no_cid(self):
        from agents.resilience.correlation import CorrelationFilter, _correlation_id_var

        f = CorrelationFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        _correlation_id_var.set("")
        assert f.filter(record) is True
        assert record.correlation_id == ""

    def test_filter_always_returns_true(self):
        from agents.resilience.correlation import CorrelationFilter

        f = CorrelationFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_context_isolation(self):
        import asyncio
        from agents.resilience.correlation import set_correlation_id, get_correlation_id

        async def task_a():
            set_correlation_id("AAAA")
            await asyncio.sleep(0.05)
            return get_correlation_id()

        async def task_b():
            set_correlation_id("BBBB")
            await asyncio.sleep(0.05)
            return get_correlation_id()

        async def main():
            results = await asyncio.gather(task_a(), task_b())
            return results

        a, b = asyncio.run(main())
        assert a == "AAAA"
        assert b == "BBBB"
        assert a != b
