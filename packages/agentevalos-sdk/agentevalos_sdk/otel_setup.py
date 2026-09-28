"""OpenTelemetry / OpenInference-compatible tracing setup, shared by both services.

Uses vendor-neutral OTLP export so traces can flow to Arize Phoenix, Future AGI's
traceAI backend, or any other OTLP collector without code changes — only the
OTEL_EXPORTER_OTLP_ENDPOINT env var changes.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(service_name: str) -> trace.Tracer:
    """Set the global TracerProvider and return a Tracer for `service_name`.

    Span attributes follow OpenInference semantic conventions (`openinference.span.kind`,
    `input.value`, `output.value`, `llm.*`, `tool.*`) so traces render correctly in
    Phoenix/Future AGI without a translation layer. Instrumented call sites (LangGraph
    nodes, MCP tool calls) are responsible for setting those attributes on their spans.
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


def instrument_fastapi(app, service_name: str) -> None:
    """Attach FastAPI auto-instrumentation. Call after configure_tracing()."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    configure_tracing(service_name)
    FastAPIInstrumentor.instrument_app(app)
