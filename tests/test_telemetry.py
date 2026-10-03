"""Telemetry export (api/telemetry.py) and the pipeline's own spans (core/pipeline.py, core/web.py).

Four properties, each of which breaks silently — a trace that is wrong still renders:

- Off by default. Without OTEL_EXPORTER_OTLP_ENDPOINT nothing is installed and nothing is sent, so
  tests, scripts and a laptop with no collector are unaffected.
- Branch spans nest. The pipeline fans out to worker threads; a span that loses its parent there
  becomes its own root trace, and "which branch took the time" is no longer answerable.
- No credential reaches a trace. The sign-in callback's query string carries the Entra code.
- Shipping logs does not silence stderr, which is where the platform collects them today.

Every test here uses its own in-memory provider rather than the global one, so nothing leaks into
the rest of the suite.
"""
import concurrent.futures
import logging
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import telemetry  # noqa: E402
from core import pipeline, web  # noqa: E402


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_off_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    called = []
    monkeypatch.setattr(telemetry, "_install", lambda app: called.append(app))
    assert telemetry.setup_telemetry(FastAPI()) is False
    assert called == []


def test_a_failed_setup_does_not_stop_the_api(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    def boom(app):
        raise RuntimeError("collector config broken")
    monkeypatch.setattr(telemetry, "_install", boom)
    assert telemetry.setup_telemetry(FastAPI()) is False


def test_branch_spans_keep_their_parent_across_worker_threads(spans, monkeypatch):
    provider, exporter = spans
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(pipeline, "_tracer", tracer)

    def branch():
        with tracer.start_as_current_span("completion"):
            return "ok"

    with tracer.start_as_current_span("evaluate"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            assert pipeline._submit(ex, "pipeline.profile", branch).result() == "ok"

    by_name = {s.name: s for s in exporter.get_finished_spans()}
    assert by_name["pipeline.profile"].parent.span_id == by_name["evaluate"].context.span_id
    assert by_name["completion"].parent.span_id == by_name["pipeline.profile"].context.span_id
    assert len({s.context.trace_id for s in by_name.values()}) == 1


def test_a_failing_branch_is_recorded_as_an_error_and_still_raises(spans, monkeypatch):
    provider, exporter = spans
    monkeypatch.setattr(pipeline, "_tracer", provider.get_tracer("test"))

    def branch():
        raise ValueError("model returned garbage")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        with pytest.raises(ValueError):
            pipeline._submit(ex, "pipeline.trend", branch).result()
    (span,) = exporter.get_finished_spans()
    assert span.status.status_code.name == "ERROR"


def test_a_cached_search_is_marked_as_one(spans, monkeypatch):
    provider, exporter = spans
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(web, "_cached", lambda kind, key, meta=None: [{"href": "https://x.test"}])

    # ddg_search's decorator was bound at import; run it under a current span of ours instead,
    # which is exactly what the decorator provides.
    with tracer.start_as_current_span("web.search"):
        web.ddg_search.__wrapped__("acme robotics funding")
    (span,) = exporter.get_finished_spans()
    assert span.attributes["web.search.cache_hit"] is True
    assert span.attributes["web.search.query"] == "acme robotics funding"


def test_the_sign_in_callback_never_reaches_a_trace(spans):
    provider, exporter = spans
    app = FastAPI()

    @app.get("/api/auth/callback")
    def callback(code: str = "", state: str = ""):
        return {}

    @app.get("/api/runs")
    def runs():
        return []

    telemetry.instrument_app(app, tracer_provider=provider)
    client = TestClient(app)
    client.get("/api/auth/callback?code=SECRET-AUTH-CODE&state=s")
    client.get("/api/runs")

    finished = exporter.get_finished_spans()
    assert finished, "the ordinary route should still be traced"
    assert all("SECRET-AUTH-CODE" not in str(dict(s.attributes)) for s in finished)
    assert all("callback" not in s.name for s in finished)


def test_shipping_logs_does_not_silence_stderr(capsys):
    # A fresh logger stands in for the unconfigured root: no handlers, WARNING by default, so
    # until now its warnings reached stderr only through Python's last-resort handler.
    root = logging.Logger("stand-in-root", level=logging.WARNING)
    shipped = []

    class Collect(logging.Handler):
        def emit(self, record):
            shipped.append(record.getMessage())

    telemetry.attach_log_handler(root, Collect(level=logging.INFO))
    root.info("pipeline started")
    root.warning("GlassDollar unreachable")

    err = capsys.readouterr().err
    assert "GlassDollar unreachable" in err
    assert "pipeline started" not in err      # stderr stays at WARNING, as before
    assert shipped == ["pipeline started", "GlassDollar unreachable"]
