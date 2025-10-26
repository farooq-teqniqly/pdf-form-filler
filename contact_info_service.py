import json


class ContactInfoService:
    """Service for retrieving and enriching company contact information using OpenAI.

    This class provides functionality to look up official contact details
    for companies (address, city, state, website/email, phone) using OpenAI's
    search capabilities and JSON schema validation.
    """
    __CONTACT_INFO_FORMAT = {
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
            Exception: If openai_client is None.
        """
        if openai_client is None:
            raise Exception("openai_client must be provided")

        self.open_ai_client = openai_client

    def __get_user_prompt(self, business_name: str) -> str:
        return f"""
        Find the official contact information for the company named "{business_name}".
    
        You must determine the company’s:
        1. Street address (headquarters or main office)
        2. City
        3. State or province (if applicable)
        4. Official website URL
        5. Phone number (if applicable)
        6. Source URL's of the sources you used.
    
        Follow these rules:
    
        1. Use authoritative and trustworthy sources such as:
           - The company’s official website (preferred)
           - LinkedIn company pages
           - Business registries (e.g., SEC filings, government listings)
           - Reliable business directories (Crunchbase, Bloomberg, etc.)
    
        2. The "website" field must always be the company’s **official domain** — not a LinkedIn or directory page.
           For example, if the company is “Acuity Brands”, the website should be `https://www.acuitybrands.com`.
    
        3. The "address" should be the **primary headquarters** address, not a branch office or distributor.
           Include street number and name where available (e.g., "1170 Peachtree Street NE").
    
        4. If you find multiple addresses or conflicting information:
           - Prefer the one listed on the company’s official site.
           - Otherwise, prefer the headquarters location listed by multiple reliable sources.
           - A United States address, if one exists, should take precendece.
    
        5. If the company cannot be found or lacks sufficient information to determine an address and website:
           Return only a JSON object with an `"error"` key and a clear message, e.g.:
           {{
        "error": "No company named '{business_name}' could be found."
           }}
    
        Follow the provided JSON schema exactly.
        """

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
        """
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

        data = json.loads(response.output_text)

        return data
