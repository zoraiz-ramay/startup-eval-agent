"""OpenTelemetry export to SigNoz (or any OTLP collector): traces, metrics and logs.

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set, so tests, scripts and a laptop without a collector
pay nothing and send nothing. Everything else is the standard OTEL_* environment, read by the
exporters themselves:

  self-hosted SigNoz   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
  SigNoz Cloud         OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.<region>.signoz.cloud:443
                       OTEL_EXPORTER_OTLP_HEADERS=signoz-ingestion-key=<key>

Called once per process from api/main.py. gunicorn imports the app in each worker after the fork
(start.sh does not --preload), so every worker gets its own exporter threads — which is what the
SDK needs; a provider created before a fork exports from a thread the child does not have.
"""
from __future__ import annotations

import importlib
import logging
import os

log = logging.getLogger(__name__)

# /api/auth/callback carries the Entra authorization code in its query string, and the ASGI
# instrumentation records the full URL. A spent code is useless, but a credential in a telemetry
# store is exactly what an audit flags, and the session it mints is the thing worth protecting.
# /health is the container probe every 30s: pure noise.
_EXCLUDED_URLS = "/health,/api/auth/callback"


def setup_telemetry(app) -> bool:
    """Instrument the app and install exporters. Returns whether telemetry is on."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        return False
    try:
        _install(app)
    except Exception:
        # Observability must never be the reason the API does not start.
        log.exception("telemetry: setup failed; continuing without it")
        return False
    log.info("telemetry: exporting to %s", os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
    return True


def instrument_app(app, tracer_provider=None) -> None:
    """Server spans for every request. Separate from _install so a test can drive it against an
    in-memory provider instead of the global one."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    # receive/send would add a child span per SSE event on /api/evaluate/stream.
    FastAPIInstrumentor.instrument_app(app, excluded_urls=_EXCLUDED_URLS,
                                       exclude_spans=["receive", "send"],
                                       tracer_provider=tracer_provider)


def attach_log_handler(root: logging.Logger, handler: logging.Handler) -> None:
    """Ship INFO and above through ``handler`` without changing what reaches stderr."""
    # Nothing configures the root logger today, so warnings reach the container log only through
    # Python's last-resort stderr handler — which stops firing the moment the root has ANY
    # handler. Without this stand-in, switching telemetry on would silently empty the platform's
    # log stream of every app warning and error.
    if not root.handlers:
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        root.addHandler(console)
    root.addHandler(handler)
    # The root logger defaults to WARNING, which would drop the app's own log.info lines before
    # they reached the handler; the console handler above keeps stderr at WARNING regardless.
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)


def _install(app) -> None:
    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES still win: Resource.create merges the
    # environment over these defaults.
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "startup-eval-agent"),
        "deployment.environment": os.getenv("APP_ENV", "development"),
    })

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(MeterProvider(
        resource=resource, metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())]))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    attach_log_handler(logging.getLogger(),
                       LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    # httpx logs every request at INFO; the httpx spans already carry it.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    instrument_app(app)
    # Each library separately: these packages patch third-party code and break on version drift
    # (openai-v2 broke on wrapt 2), and one broken library should cost its own spans, not all of
    # them.
    for name in _LIBRARIES:
        try:
            module, cls = name.rsplit(":", 1)
            getattr(importlib.import_module(module), cls)().instrument()
        except Exception:
            log.warning("telemetry: could not instrument %s", name, exc_info=True)


_LIBRARIES = (
    "opentelemetry.instrumentation.requests:RequestsInstrumentor",   # GlassDollar, Tracxn, sites
    "opentelemetry.instrumentation.httpx:HTTPXClientInstrumentor",   # the OpenAI SDK's transport
    "opentelemetry.instrumentation.botocore:BotocoreInstrumentor",   # the S3 upload per write
    # Model, latency and token usage per completion. Prompt and completion text are NOT captured
    # unless OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true, and should stay off: prompts
    # carry the evidence the run gathered, which belongs in runs.db, not a log store.
    "opentelemetry.instrumentation.openai_v2:OpenAIInstrumentor",
    # SQLite is absent because it would record nothing: the dbapi instrumentation traces
    # cursor.execute, api/store.py calls con.execute, and the proxy it wraps every connection in
    # is pure risk for no spans. The S3 upload after each write is the slow part, and botocore
    # covers that.
    # Redis is deliberately absent: its keys are session ids, and a session id in a trace is a
    # usable credential for anyone who can read the trace.
)
