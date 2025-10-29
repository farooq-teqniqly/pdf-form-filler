# OpenTelemetry Instrumentation Plan

## Application Analysis

The application is a Python CLI tool that:

- Reads PDF forms and YAML data
- Enriches contact information via OpenAI API
- Fills PDF form fields and writes output files

### Key Areas to Instrument

#### 1. External API Calls

- OpenAI API requests in `ContactInfoService.get_contact_info()`
- Track request duration, success/failure, and errors

#### 2. File Operations

- PDF reading/writing operations
- YAML file parsing
- Track file sizes and operation duration

#### 3. Business Logic

- Contact enrichment loop (3 contacts per form)
- Form field filling operations
- Track processing time per contact

#### 4. Error Scenarios

- PDF read errors
- OpenAI API failures
- Missing contact information
- Validation errors

### Implementation Approach

#### Phase 1: Setup & Dependencies

1. Add OpenTelemetry packages to `requirements.txt`:

   - `opentelemetry-api`
   - `opentelemetry-sdk`
   - `opentelemetry-instrumentation-openai` (auto-instrumentation for OpenAI)
   - `opentelemetry-exporter-otlp` (for exporting to collectors)
   - Optional: `opentelemetry-exporter-console` (for development/debugging)

#### Phase 2: Core Instrumentation

1. Create a new module `telemetry.py` to configure OpenTelemetry:

   - Initialize tracer provider
   - Configure exporters (OTLP and/or console)
   - Set up resource attributes (service name, version, etc.)
   - Configure sampling strategy

2. Add manual instrumentation to `fill_esd_log.py`:

   - Create root span for `main()` function

   - Add spans for major operations:

     - YAML loading
     - PDF reading
     - Contact enrichment loop
     - PDF writing

   - Add span attributes (contact count, PDF paths, etc.)

   - Record exceptions in spans

3. Instrument `contact_info_service.py`:

   - Add span for `get_contact_info()` method
   - Track business_name as attribute
   - Record API response status (success/error)
   - Add custom metrics for API call duration

#### Phase 3: Metrics & Context

1. Add custom metrics:

   - Counter: Total PDFs processed
   - Counter: Total contacts enriched
   - Counter: OpenAI API failures
   - Histogram: PDF processing duration
   - Histogram: Contact enrichment duration

2. Add contextual attributes:

   - Service metadata (version, environment)
   - Input/output file paths
   - Contact processing results
   - Error types and messages

#### Phase 4: Configuration

1. Make telemetry configurable via environment variables:

   - `OTEL_EXPORTER_OTLP_ENDPOINT` (collector URL)
   - `OTEL_SERVICE_NAME` (default: "pdf-form-filler")
   - `OTEL_TRACES_EXPORTER` (otlp/console/none)
   - `OTEL_METRICS_EXPORTER` (otlp/console/none)
   - `ENABLE_TELEMETRY` (opt-in/out flag)

2. Update `.env.example` with telemetry configuration options

### Benefits of This Approach

- **Observability**: Track PDF processing pipeline end-to-end
- **Performance**: Identify bottlenecks (OpenAI API calls, PDF operations)
- **Reliability**: Monitor error rates and failure patterns
- **Debugging**: Detailed traces for troubleshooting issues
- **Compliance**: Track all external API calls for audit purposes

### Technical Considerations

1. **Automatic vs Manual Instrumentation**:

   - Use auto-instrumentation for OpenAI SDK (simpler, less code)
   - Use manual instrumentation for custom business logic

2. **Sampling Strategy**:

   - For CLI tool, recommend 100% sampling (each invocation is important)
   - Can be configured via environment variable

3. **Exporter Choice**:

   - OTLP exporter for production (works with Jaeger, Zipkin, etc.)
   - Console exporter for development/testing
   - Support both simultaneously

4. **Performance Impact**:

   - Minimal for CLI tool (each run is independent)
   - Telemetry overhead is negligible compared to OpenAI API calls
