# OpenTelemetry Instrumentation Guide

This document provides detailed information about the OpenTelemetry instrumentation implemented in the PDF Form Filler application.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Trace Hierarchy](#trace-hierarchy)
- [Span Attributes](#span-attributes)
- [Metrics](#metrics)
  - [Available Metrics](#available-metrics)
  - [Metrics Export](#metrics-export)
  - [Example Queries](#example-queries)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Configuration Examples](#configuration-examples)
- [Error Handling](#error-handling)
  - [Error Types Tracked](#error-types-tracked)
  - [Exception Recording](#exception-recording)
- [Performance Considerations](#performance-considerations)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Future Enhancements](#future-enhancements)
- [Resources](#resources)

## Overview

The application uses OpenTelemetry to provide comprehensive observability into the PDF processing pipeline, including:

- Distributed tracing for all major operations
- Automatic instrumentation of OpenAI API calls
- Error tracking and exception recording
- Performance monitoring
- Custom metrics (counters and histograms)
- Duration tracking for operations

## Architecture

### Components

1. **telemetry.py** - Core configuration module

   - Initializes OpenTelemetry tracer provider
   - Configures OTLP gRPC exporter
   - Enables auto-instrumentation for OpenAI SDK
   - Provides tracer instance for manual instrumentation

2. **fill_esd_log.py** - Main application instrumentation

   - Root span for entire PDF filling operation
   - Nested spans for each major operation
   - Detailed attributes for file paths and processing status

3. **contact_info_service.py** - Service instrumentation
   - Spans for contact information lookup
   - Success/failure tracking
   - Error type classification

## Trace Hierarchy

```text
fill_pdf_form (root span)
├── load_yaml_data
│   └── attributes: file.path, contacts.count
├── read_pdf
│   └── attributes: file.path
├── enrich_contacts
│   ├── enrich_contact_1
│   │   └── attributes: business_name, enrichment.success
│   ├── enrich_contact_2
│   │   └── attributes: business_name, enrichment.success
│   └── enrich_contact_3
│       └── attributes: business_name, enrichment.success
│       └── get_contact_info (from ContactInfoService)
│           └── attributes: business_name, lookup.success
│           └── [OpenAI API call - auto-instrumented]
└── write_pdf
    └── attributes: file.path
```

## Span Attributes

### Root Span (fill_pdf_form)

- `pdf.input_path`: Path to input PDF file
- `pdf.output_path`: Path to output PDF file
- `yaml.input_path`: Path to YAML data file
- `pdf.processing_complete`: Boolean indicating success

### YAML Loading (load_yaml_data)

- `file.path`: YAML file path
- `contacts.count`: Number of contacts in YAML data

### PDF Operations (read_pdf, write_pdf)

- `file.path`: PDF file path

### Contact Enrichment (enrich_contacts)

- `contacts.total`: Total number of contact blocks (always 3)
- `contacts.provided`: Actual number of contacts in YAML

### Individual Contact (enrich_contact_N)

- `contact.index`: Contact number (1, 2, or 3)
- `contact.business_name`: Company name being looked up
- `enrichment.success`: Boolean indicating if enrichment succeeded
- `enrichment.error`: Error message if enrichment failed

### Contact Info Lookup (get_contact_info)

- `business_name`: Company being looked up
- `lookup.success`: Boolean indicating lookup success
- `result.city`: City from lookup result
- `result.state`: State from lookup result
- `error.type`: Type of error (api_error, json_decode_error, business_not_found, missing_fields)
- `error.message`: Detailed error message

## Metrics

The application exports custom metrics to track key performance indicators and operational statistics.

### Available Metrics

#### Counters

1. **pdf.processed.total**

   - Description: Total number of PDFs processed
   - Unit: `1` (count)
   - Attributes:
     - `status`: Processing status (`success` or `failure`)
   - Use case: Track overall PDF processing volume and success rate

2. **contact.enriched.total**

   - Description: Total number of contacts successfully enriched
   - Unit: `1` (count)
   - Attributes:
     - `business_name`: Name of the company looked up
   - Use case: Monitor contact enrichment success rate

3. **contact.enrichment.failed.total**
   - Description: Total number of contact enrichment failures
   - Unit: `1` (count)
   - Attributes:
     - `error_type`: Type of error (`business_not_found`, `exception`)
     - `business_name`: Name of the company that failed
   - Use case: Identify problematic companies and error patterns

#### Histograms

1. **pdf.processing.duration**

   - Description: Duration of PDF processing operations (end-to-end)
   - Unit: `ms` (milliseconds)
   - Attributes:
     - `status`: Processing status (`success` or `failure`)
   - Use case: Monitor performance and identify slow processing

2. **contact.enrichment.duration**
   - Description: Duration of individual contact enrichment operations
   - Unit: `ms` (milliseconds)
   - Attributes:
     - `contact_index`: Contact number (`1`, `2`, or `3`)
     - `business_name`: Name of the company looked up
   - Use case: Identify slow API calls and optimize performance

### Metrics Export

- Metrics are exported every 60 seconds by default
- Uses OTLP gRPC protocol to the configured endpoint
- Metrics share the same endpoint as traces (`OTEL_EXPORTER_OTLP_ENDPOINT`)

### Example Queries

When using metrics with your observability backend, you can create useful queries:

**Success Rate**:

```text
rate(pdf.processed.total{status="success"}) / rate(pdf.processed.total)
```

**Average Processing Time**:

```text
avg(pdf.processing.duration)
```

**Contact Enrichment Failure Rate**:

```text
rate(contact.enrichment.failed.total) / (rate(contact.enriched.total) + rate(contact.enrichment.failed.total))
```

**95th Percentile Enrichment Duration**:

```text
histogram_quantile(0.95, contact.enrichment.duration)
```

## Configuration

### Environment Variables

| Variable                      | Default                 | Description                                                             |
| ----------------------------- | ----------------------- | ----------------------------------------------------------------------- |
| `ENABLE_TELEMETRY`            | `true`                  | Enable/disable telemetry collection                                     |
| `OTEL_SERVICE_NAME`           | `pdf-form-filler`       | Service name in traces                                                  |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP collector endpoint (gRPC)                                          |
| `OTEL_EXPORTER_OTLP_INSECURE` | `false`                 | Use secure connection (TLS). Set to `false` for local development only. |

### Configuration Examples

#### Local Development with Aspire Dashboard (Recommended)

The .NET Aspire Dashboard provides an excellent local development experience with support for traces, metrics, and logs in a single unified UI.

```sh
# .env
ENABLE_TELEMETRY=true
OTEL_SERVICE_NAME=pdf-form-filler
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Start Aspire Dashboard:

```sh
docker run -d --name aspire-dashboard \
  -p 18888:18888 \
  -p 4317:18889 \
  mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

Then access the dashboard at `http://localhost:18888`

**Benefits:**

- Unified UI for traces, metrics, and logs
- No configuration required
- Lightweight and fast
- Real-time updates
- Built-in filtering and search

#### Local Development with Jaeger (Alternative)

```sh
# .env
ENABLE_TELEMETRY=true
OTEL_SERVICE_NAME=pdf-form-filler
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Start Jaeger:

```sh
docker run -d --name jaeger \
  -p 4317:4317 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

Then access the Jaeger UI at `http://localhost:16686`

#### Cloud Provider (e.g., Grafana Cloud)

```sh
# .env
ENABLE_TELEMETRY=true
OTEL_SERVICE_NAME=pdf-form-filler
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-central-0.grafana.net/otlp
```

#### Disable Telemetry

```sh
# .env
ENABLE_TELEMETRY=false
```

## Error Handling

### Error Types Tracked

1. **api_error** - OpenAI API call failed

   - Network issues
   - Authentication failures
   - Rate limiting

2. **json_decode_error** - Invalid JSON response from OpenAI

   - Malformed response
   - Unexpected format

3. **business_not_found** - Company not found

   - Company doesn't exist
   - Insufficient information available

4. **missing_fields** - Response missing required fields
   - Incomplete data from OpenAI
   - Schema validation failure

### Exception Recording

All exceptions are recorded with:

- Exception type
- Exception message
- Stack trace
- Span status set to ERROR

## Performance Considerations

### Overhead

- **Minimal overhead** when enabled (~1-2% CPU, <10MB memory)
- **Zero overhead** when disabled (no-op tracer)
- Batch span processor reduces network calls
- Auto-instrumentation adds negligible latency

### Sampling

- Currently set to 100% sampling (all traces captured)
- Suitable for CLI tool with discrete executions
- Can be configured via OTLP collector for production

## Troubleshooting

### Traces Not Appearing

1. **Check telemetry is enabled**

   ```sh
   # Should be true or not set
   ENABLE_TELEMETRY=true
   ```

2. **Verify OTLP endpoint is reachable**

   ```sh
   # Test connectivity
   grpcurl localhost:4317
   ```

3. **Check collector logs**

   ```sh
   # For Docker Jaeger
   docker logs jaeger
   ```

### Common Issues

**Issue**: `ConnectionRefusedError` when exporting spans

**Solution**: Ensure OTLP collector is running and accessible at the configured endpoint.

---

**Issue**: Spans appear but are missing attributes

**Solution**: Check that the application is using the latest version of the code with full instrumentation.

---

**Issue**: High memory usage

**Solution**: Batch span processor may be buffering too many spans. Check collector availability.

## Best Practices

1. **Always set service name** to identify your application in multi-service environments
2. **Use consistent attribute naming** following OpenTelemetry semantic conventions
3. **Record meaningful errors** with context for debugging
4. **Flush spans on shutdown** using `shutdown_telemetry()` to avoid data loss
5. **Monitor collector health** to ensure spans are being exported

## Future Enhancements

Potential improvements for observability:

1. ### Logging: Integrate OpenTelemetry logging

   - Correlate logs with traces
   - Structured logging with trace context

2. ### Baggage: Propagate user context

   - User ID
   - Session information
   - Processing metadata

3. ### Sampling: Implement adaptive sampling

   - Sample based on error conditions
   - Priority sampling for important operations

## Resources

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
