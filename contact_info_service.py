import json
from typing import ClassVar
from telemetry import tracer, tokens_total, tokens_per_request
from opentelemetry.trace import Status, StatusCode
from jsonschema import validate, ValidationError
import telemetry_constants


class ContactInfoServiceError(Exception):
    """Exception raised when ContactInfoService initialization or operation
    fails."""


class ContactInfoService:
    """Service for retrieving and enriching company contact information using
    OpenAI.

    This class provides functionality to look up official contact
    details for companies (address, city, state, website/email, phone)
    using OpenAI's search capabilities and JSON schema validation.
    """

    __CONTACT_INFO_FORMAT: ClassVar[dict] = {
        "format": {
            "type": "json_schema",
            "name": "contact_info_response",
            "schema": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Contact's address"},
                    "city": {"type": "string", "description": "Contact's city"},
                    "state": {"type": "string", "description": "Contact's state"},
                    "website_or_email": {
                        "type": "string",
                        "description": "Contact's website or email",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Contact's phone",
                        "pattern": "^\\(\\d{3}\\) \\d{3}-\\d{4}$",
                    },
                    "source_urls": {
                        "type": "array",
                        "description": "List of URLs associated with the contact's source",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "address",
                    "city",
                    "state",
                    "website_or_email",
                    "phone",
                    "source_urls",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }
    }

    def __init__(self, openai_client):
        """Initialize the ContactInfoService with an OpenAI client.

        Args:
            openai_client: An instance of the OpenAI client used for API calls.

        Raises:
            ContactInfoServiceError: If openai_client is None.
        """
        if openai_client is None:
            raise ContactInfoServiceError("openai_client must be provided")

        self.open_ai_client = openai_client

    def __get_user_prompt(self, business_name: str) -> str:
        return f"""
        Find the official contact information for the company named "{business_name}".
    
        You must determine the company's:
        1. Street address (headquarters or main office)
        2. City
        3. State or province (if applicable)
        4. Official website URL
        5. Phone number (if applicable)
        6. Source URL's of the sources you used.
    
        Follow these rules:
    
        1. Use authoritative and trustworthy sources such as:
           - The company's official website (preferred)
           - LinkedIn company pages
           - Business registries (e.g., SEC filings, government listings)
           - Reliable business directories (Crunchbase, Bloomberg, etc.)
    
        2. The "website" field must always be the company's **official domain** — not a LinkedIn or directory page.
           For example, if the company is “Acuity Brands”, the website should be `https://www.acuitybrands.com`.
    
        3. The "address" should be the **primary headquarters** address, not a branch office or distributor.
           Include street number and name where available (e.g., "1170 Peachtree Street NE").
    
        4. If you find multiple addresses or conflicting information:
           - Prefer the one listed on the company's official site.
           - Otherwise, prefer the headquarters location listed by multiple reliable sources.
           - A United States address, if one exists, should take precedence.
    
        5. If the company cannot be found or lacks sufficient information to determine an address and website:
           Return only a JSON object with an `"error"` key and a clear message, e.g.:
           {{
        "error": "No company named '{business_name}' could be found."
           }}
    
        Follow the provided JSON schema exactly.
        """

    def _record_token_metrics(self, response, business_name: str):
        """Record OpenAI token usage metrics for monitoring and billing.

        Extracts token usage information from the OpenAI API response and records
        both histogram (per-request distribution) and counter (cumulative total)
        metrics for observability and cost tracking.

        Args:
            response: The OpenAI API response object containing usage information.
            business_name (str): The business name being looked up, used as a metric attribute.

        Note:
            Safely handles cases where usage information is not available in the response.
            Records both tokens_per_request histogram and tokens_total counter metrics
            with model and business_name attributes for filtering and analysis.
        """
        usage = getattr(response, "usage")

        if usage is None:
            return

        tokens_used = getattr(usage, "total_tokens")

        if tokens_used is None:
            return

        model = getattr(response, "model")

        metric_attributes = {"model": model, "business_name": business_name}

        tokens_per_request.record(tokens_used, metric_attributes)
        tokens_total.add(tokens_used, metric_attributes)

    def get_contact_info(self, business_name: str):
        """Retrieve contact information for a company using OpenAI.

        Uses OpenAI's search capabilities to find official contact details
        including address, city, state, website/email, phone, and source URLs.

        Args:
            business_name (str): The name of the business to look up.

        Returns:
            dict: A dictionary containing the contact information with keys:
                - address (str): Street address
                - city (str): City
                - state (str): State
                - website_or_email (str): Official website or email
                - phone (str): Phone number in format "(XXX) XXX-XXXX"
                - source_urls (list[str]): List of source URLs used
                - error (str): Error message if lookup fails (optional)

        Raises:
            ContactInfoServiceError: If the API call fails or returns invalid data.
        """
        with tracer.start_as_current_span("get_contact_info") as span:
            span.set_attribute("business_name", business_name)

            try:
                response = self.open_ai_client.responses.create(
                    model="gpt-4o-mini",
                    tools=[{"type": "web_search"}],
                    input=[
                        {
                            "role": "user",
                            "content": f"""
                        Find the official contact information for the company named {business_name}.
                        {self.__get_user_prompt(business_name)}
                    """,
                        }
                    ],
                    text=self.__CONTACT_INFO_FORMAT,
                    metadata={"purpose": "esd_business_name_lookup"},
                )

                self._record_token_metrics(response, business_name)

            except Exception as e:
                span.set_attribute(telemetry_constants.SPAN_ATTR_LOOKUP_SUCCESS, False)
                span.set_attribute(
                    telemetry_constants.SPAN_ATTR_ERROR_TYPE, "api_error"
                )
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)

                raise ContactInfoServiceError(
                    f"OpenAI API call failed for '{business_name}': {e}"
                ) from e

            try:
                data = json.loads(response.output_text)
            except json.decoder.JSONDecodeError as e:
                span.set_attribute(telemetry_constants.SPAN_ATTR_LOOKUP_SUCCESS, False)
                span.set_attribute(
                    telemetry_constants.SPAN_ATTR_ERROR_TYPE, "json_decode_error"
                )
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)

                raise ContactInfoServiceError(
                    f"Invalid JSON response for '{business_name}': {e}"
                ) from e

            if "error" in data:
                span.set_attribute(telemetry_constants.SPAN_ATTR_LOOKUP_SUCCESS, False)
                span.set_attribute(
                    telemetry_constants.SPAN_ATTR_ERROR_TYPE, "business_not_found"
                )
                span.set_attribute("error.message", data["error"])
                return data

            required_fields = self._ContactInfoService__CONTACT_INFO_FORMAT["format"][
                "schema"
            ]["required"]

            schema = self._ContactInfoService__CONTACT_INFO_FORMAT["format"]["schema"]
            required_fields = schema["required"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                span.set_attribute(telemetry_constants.SPAN_ATTR_LOOKUP_SUCCESS, False)
                span.set_attribute(
                    telemetry_constants.SPAN_ATTR_ERROR_TYPE, "missing_fields"
                )
                span.set_attribute("error.missing_fields", ", ".join(missing_fields))
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)

                raise ContactInfoServiceError(
                    f"Response missing required fields: {', '.join(missing_fields)}"
                ) from e

            try:
                validate(data, schema)
            except ValidationError as e:
                span.set_attribute(telemetry_constants.SPAN_ATTR_LOOKUP_SUCCESS, False)
                span.set_attribute(
                    telemetry_constants.SPAN_ATTR_ERROR_TYPE, "schema_validation_error"
                )
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)

            span.set_attribute(telemetry_constants.SPAN_ATTR_LOOKUP_SUCCESS, True)
            span.set_attribute("result.city", data.get("city", ""))
            span.set_attribute("result.state", data.get("state", ""))

            return data
