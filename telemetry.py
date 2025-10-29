"""OpenTelemetry configuration and setup for PDF Form Filler.

This module initializes OpenTelemetry tracing with OTLP export and auto-
instrumentation for OpenAI API calls.
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.openai import OpenAIInstrumentor


def _is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled via environment variable.

    Returns:
        bool: True if telemetry should be enabled, False otherwise.
    """
    value = os.getenv("ENABLE_TELEMETRY", "true").strip().lower()
    return value not in ("", "0", "false", "no", "off")


def _is_insecure_mode() -> bool:
    """Check if insecure mode (no TLS) should be used.

    Returns:
        bool: True for insecure connections (local dev), False for TLS.
    """
    value = os.getenv("OTEL_EXPORTER_INSECURE", "true").strip().lower()
    return value in ("1", "true", "yes", "on")


def _get_service_name() -> str:
    """Get the service name from environment or use default.

    Returns:
        str: The service name to use for telemetry.
    """
    return os.getenv("OTEL_SERVICE_NAME", "pdf-form-filler")


def _get_service_version() -> str:
    """Get the service version from environment or use default.

    Returns:
        str: The service version to use for telemetry.
    """
    return os.getenv("OTEL_SERVICE_VERSION", "1.0.0")


def _get_otlp_endpoint() -> str:
    """Get the OTLP exporter endpoint from environment or use default.

    Returns:
        str: The OTLP endpoint URL.
    """
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")


def _setup_telemetry() -> trace.Tracer:
    """Initialize OpenTelemetry tracing with OTLP export.

    Sets up:
    - Tracer provider with resource attributes
    - OTLP span exporter
    - Batch span processor
    - Auto-instrumentation for OpenAI

    Returns:
        trace.Tracer: Configured tracer instance.
    """
    if not _is_telemetry_enabled():
        # Return a no-op tracer if telemetry is disabled
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        return trace.get_tracer(__name__)

    # Create resource with service identification
    resource = Resource.create(
        {
            "service.name": _get_service_name(),
            "service.version": "1.0.0",
        }
    )

    # Set up tracer provider
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=_get_otlp_endpoint(), insecure=_is_insecure_mode()
    )

    # Add batch span processor for efficient export
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Enable auto-instrumentation for OpenAI
    OpenAIInstrumentor().instrument()

    return trace.get_tracer(__name__)


def shutdown_telemetry() -> None:
    """Flush and shutdown the tracer provider.

    This ensures all pending spans are exported before the application
    exits. Call this at the end of the application lifecycle.
    """
    if _is_telemetry_enabled():
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()


# Initialize tracer on module import
tracer = _setup_telemetry()
