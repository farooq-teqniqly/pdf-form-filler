"""OpenTelemetry span attribute constants for PDF Form Filler.

This module defines standardized attribute keys for OpenTelemetry spans
to ensure consistent telemetry data across the application. These
constants help maintain uniform attribute naming and prevent typos in
span attributes.
"""

# Span attribute for tracking lookup operation success/failure
SPAN_ATTR_LOOKUP_SUCCESS: str = "lookup.success"

# Span attribute for categorizing error types (e.g., "api_error", "json_decode_error")
SPAN_ATTR_ERROR_TYPE: str = "error.type"

# Span attribute for file path being processed
SPAN_ATTR_FILE_PATH: str = "file.path"

# Span attribute for tracking contact enrichment operation success/failure
SPAN_ATTR_ENRICHMENT_SUCCESS: str = "enrichment.success"
