# PDF Form Filler

PDF Form Filler is a command-line tool for automatically filling out weekly job-search log PDF forms using structured YAML data. It leverages AI to look up and fill company contact information based on business names, making it easy to generate completed forms for submission. Designed for quick setup and use by developers.

## Features

- Fill out job-search log PDFs using YAML data
- AI-powered lookup of company contact information (address, city, state, website/email, phone) using OpenAI
- Simple command-line interface
- Utility script to extract field names from PDFs
- Easily extensible and customizable

## Getting Started

### Prerequisites

- Python 3.12 or later
- [pip](https://pip.pypa.io/en/stable/)
- OpenAI API key (set via .env file as `OPENAI_API_KEY`)

### Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/farooq-teqniqly/pdf-form-filler.git
   cd pdf-form-filler
   ```

2. (Recommended) Create and activate a virtual environment:

   ```sh
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

4. Set up environment variables: Create a `.env` file in the project root with your configuration:

   ```sh
   # Required: OpenAI API key
   OPENAI_API_KEY=your_openai_api_key_here

   # Optional: OpenTelemetry configuration
   ENABLE_TELEMETRY=true
   OTEL_SERVICE_NAME=pdf-form-filler
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   ```

## Usage

### Prepare Your Files

- **Blank PDF**: A blank job-search log PDF form is included in the repository as `ESD-job-search-log-blank.pdf`. This PDF has been prepared with appropriately named fields (e.g., "name", "ssn", "week-ending", "c1-contact-date", etc.). Use `get_fields.py` to inspect and verify field names in any other PDF you use.
- **YAML Data File**: Contains the weekly job-search data (see `week.yaml` for an example).

### Filler Script

Fill the PDF form using the following command:

```sh
python fill_esd_log.py <blank.pdf> <week.yaml> <output.pdf>
```

#### Example

```sh
python fill_esd_log.py ESD-job-search-log-blank.pdf week.yaml filled_log.pdf
```

This will read the YAML data, use AI to look up missing contact information for each business_name, and fill the PDF accordingly.

### Utility Script: Extract PDF Fields

To list all field names in a PDF form, use the utility script:

```sh
python get_fields.py <blank.pdf>
```

#### Fill Example

```sh
python get_fields.py ESD-job-search-log-blank.pdf
```

This is useful for preparing or verifying the PDF has the correct field names.

### YAML Data Example

See `week.yaml` for a sample structure. Provide at least 3 contacts. The tool will automatically look up company contact information based on `business_name` using OpenAI.

```yaml
name: "John Doe"
ssn: "XXX-XX-XXXX"
week_ending: "10/25/2025"
contacts:
  - date: "09/08/2025"
    activity_choice: "employer contact"
    business_name: "Evergreen Tech Solutions"
    job_title: "Senior Software Engineer"
    contact_method: ["Online"]
    contact_type: "application/resume"
  # ... add at least 3 contacts
```

## Observability with OpenTelemetry

This application is instrumented with OpenTelemetry to provide comprehensive observability into PDF processing operations.

### What is Instrumented

The application automatically traces:

1. **PDF Processing Pipeline**

   - YAML data loading
   - PDF reading and writing
   - Form field population

2. **Contact Enrichment**

   - OpenAI API calls for company information lookup
   - Success/failure tracking
   - Individual contact processing

3. **Error Tracking**
   - API failures
   - Missing business information
   - Data validation errors

### Telemetry Configuration

Configure telemetry through environment variables in your `.env` file:

```sh
# Enable/disable telemetry (default: true)
ENABLE_TELEMETRY=true

# Service name in traces (default: pdf-form-filler)
OTEL_SERVICE_NAME=pdf-form-filler

# OTLP collector endpoint (default: http://localhost:4317)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Viewing Traces

To view traces, you need an OpenTelemetry-compatible backend such as:

- **Jaeger**: Distributed tracing platform
- **Zipkin**: Distributed tracing system
- **Grafana Tempo**: High-scale distributed tracing backend
- **Cloud providers**: AWS X-Ray, Google Cloud Trace, Azure Monitor

#### Quick Start with Jaeger (Docker)

Run Jaeger locally using Docker:

```sh
docker run -d --name jaeger \
  -p 4317:4317 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

Then access the Jaeger UI at `http://localhost:16686` to view traces.

### Trace Information

Each trace includes:

- **Span attributes**: File paths, contact counts, business names
- **Timing information**: Duration of each operation
- **Error details**: Exception messages and stack traces
- **Success indicators**: Whether operations completed successfully

### Disabling Telemetry

To disable telemetry, set `ENABLE_TELEMETRY=false` in your `.env` file. The application will use a no-op tracer with zero performance overhead.

## Development & Contribution

1. Fork this repository and clone your fork.
2. Create a new branch for your feature or bugfix.
3. Make your changes and add tests if applicable.
4. Submit a pull request with a clear description of your changes.

### Code Style

- This project uses [black](https://black.readthedocs.io/) and [docformatter](https://github.com/PyCQA/docformatter) for code formatting.
- Run `black .` and `docformatter .` before submitting a PR.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
