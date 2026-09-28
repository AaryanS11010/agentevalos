# Sends traces to Phoenix (or any OTLP collector) so we can see what the agent did.
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(service_name: str) -> trace.Tracer:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


def instrument_fastapi(app, service_name: str) -> None:
    """Turn on tracing and auto-instrument every FastAPI request."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    configure_tracing(service_name)
    FastAPIInstrumentor.instrument_app(app)
