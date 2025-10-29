"""OpenTelemetry configuration and setup for PDF Form Filler.

This module initializes OpenTelemetry tracing with OTLP export and auto-
instrumentation for OpenAI API calls.
"""

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
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


def _create_resource() -> Resource:
    resource = Resource.create(
        {
            "service.name": _get_service_name(),
            "service.version": _get_service_version(),
        }
    )
    return resource


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
    resource = _create_resource()

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


def _setup_metrics() -> metrics.Meter:
    """Initialize OpenTelemetry metrics with OTLP export.

    Sets up:
    - Meter provider with resource attributes
    - OTLP metric exporter
    - Periodic exporting metric reader

    Returns:
        metrics.Meter: Configured meter instance.
    """
    if not _is_telemetry_enabled():
        # Return a no-op meter if telemetry is disabled
        metrics.set_meter_provider(metrics.NoOpMeterProvider())
        return metrics.get_meter(__name__)

    # Create resource with service identification
    resource = _create_resource()

    # Configure OTLP metric exporter
    metric_exporter = OTLPMetricExporter(
        endpoint=_get_otlp_endpoint(), insecure=_is_insecure_mode()
    )

    # Create metric reader with periodic export (every 60 seconds)
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter, export_interval_millis=60000
    )

    # Set up meter provider
    provider = MeterProvider(resource=resource, metric_readers=[metric_reader])

    # Set as global meter provider
    metrics.set_meter_provider(provider)

    return metrics.get_meter(__name__)


def shutdown_telemetry() -> None:
    """Flush and shutdown the tracer and meter providers.

    This ensures all pending spans and metrics are exported before the
    application exits. Call this at the end of the application
    lifecycle.
    """
    if _is_telemetry_enabled():
        # Shutdown tracer provider
        trace_provider = trace.get_tracer_provider()

        if hasattr(trace_provider, "shutdown"):
            trace_provider.shutdown()

        # Shutdown meter provider
        meter_provider = metrics.get_meter_provider()

        if hasattr(meter_provider, "shutdown"):
            meter_provider.shutdown()


# Initialize tracer and meter on module import
tracer = _setup_telemetry()
meter = _setup_metrics()

# Create metric instruments
pdf_processed_counter = meter.create_counter(
    name="pdf.processed.total",
    description="Total number of PDFs processed",
    unit="1",
)

contact_enriched_counter = meter.create_counter(
    name="contact.enriched.total",
    description="Total number of contacts enriched",
    unit="1",
)

contact_enrichment_failed_counter = meter.create_counter(
    name="contact.enrichment.failed.total",
    description="Total number of contact enrichment failures",
    unit="1",
)

pdf_processing_duration = meter.create_histogram(
    name="pdf.processing.duration",
    description="Duration of PDF processing operations",
    unit="ms",
)

contact_enrichment_duration = meter.create_histogram(
    name="contact.enrichment.duration",
    description="Duration of contact enrichment operations",
    unit="ms",
)
