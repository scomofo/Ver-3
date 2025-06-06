# app/services/api_clients/maintain_quotes_api.py
import logging
from typing import Optional, Dict, Any

from app.core.result import Result
from app.core.exceptions import BRIDealException
# Assuming Config class is in app.core.config
from app.core.config import BRIDealConfig, get_config
# Assuming JDQuoteApiClient is the actual client making HTTP calls
from app.services.api_clients.jd_quote_client import JDQuoteApiClient

logger = logging.getLogger(__name__)

class MaintainQuotesAPI:
    """
    A service layer that uses JDQuoteApiClient to interact with an external
    system for maintaining quotes (e.g., John Deere's quoting system).
    This class orchestrates calls to the JDQuoteApiClient.
    """
    def __init__(self, config: BRIDealConfig, jd_quote_api_client: Optional[JDQuoteApiClient] = None):
        """
        Initializes the MaintainQuotesAPI.

        Args:
            config (Config): The application's configuration object.
            jd_quote_api_client (Optional[JDQuoteApiClient]): The API client for JD quotes.
        """
        self.config = config
        self.jd_quote_api_client = jd_quote_api_client
        self.is_operational: bool = False

        if not self.config:
            logger.error("MaintainQuotesAPI: BRIDealConfig object not provided. API will be non-functional.")
            return # Cannot proceed without config

        if self.jd_quote_api_client:
            if self.jd_quote_api_client.is_operational:
                self.is_operational = True
                logger.info("MaintainQuotesAPI initialized and operational (JDQuoteApiClient is available and operational).")
            else:
                logger.warning("MaintainQuotesAPI: JDQuoteApiClient is provided but not operational. API will be non-functional.")
        else:
            logger.warning("MaintainQuotesAPI: JDQuoteApiClient is not provided. API will be non-functional.")
            # self.is_operational remains False

    def create_quote_in_external_system(self, quote_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Creates a new quote in the external John Deere system using the API client.

        Args:
            quote_payload (Dict[str, Any]): The data for the new quote.

        Returns:
            Optional[Dict[str, Any]]: The response from the external system (e.g., new quote ID), or None on failure.
        """
        if not self.is_operational:
            logger.error("MaintainQuotesAPI: Cannot create quote. Service is not operational.")
            return None
        
        if not self.jd_quote_api_client: # Should be caught by is_operational, but as safeguard
            logger.error("MaintainQuotesAPI: JDQuoteApiClient not available. Cannot create quote.")
            return None

        logger.info(f"MaintainQuotesAPI: Attempting to create quote in external system with payload: {quote_payload}")
        try:
            # Delegate the actual API call to the jd_quote_api_client
            response = self.jd_quote_api_client.submit_new_quote(quote_data=quote_payload)
            if response and response.get("id"):
                logger.info(f"MaintainQuotesAPI: Quote successfully created in external system. Response ID: {response.get('id')}")
                return response
            else:
                logger.error(f"MaintainQuotesAPI: Failed to create quote in external system or received unexpected response: {response}")
                return None
        except Exception as e:
            logger.error(f"MaintainQuotesAPI: Exception during external quote creation: {e}", exc_info=True)
            return None

    async def get_external_quote_status(self, external_quote_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the status of an existing quote from the external system.

        Args:
            external_quote_id (str): The ID of the quote in the external system.

        Returns:
            Optional[Dict[str, Any]]: The quote details/status, or None on failure.
        """
        if not self.is_operational:
            logger.error("MaintainQuotesAPI: Cannot get quote status. Service is not operational.")
            return None
        
        if not self.jd_quote_api_client:
            logger.error("MaintainQuotesAPI: JDQuoteApiClient not available. Cannot get quote status.")
            return None

        logger.info(f"MaintainQuotesAPI: Requesting status for external quote ID: {{external_quote_id}}")
        try:
            response_result: Result[Dict, BRIDealException] = await self.jd_quote_api_client.get_quote_details(quote_id=external_quote_id) # Await here
            if response_result.is_success():
                logger.info(f"MaintainQuotesAPI: Successfully retrieved status for quote {{external_quote_id}}.")
                return response_result.value # Return the actual dictionary
            else:
                logger.warning(f"MaintainQuotesAPI: Failed to get status for quote {{external_quote_id}}. Error: {{response_result.error}}")
                return None # Or an error dict: {"error": str(response_result.error)}
        except Exception as e:
            logger.error(f"MaintainQuotesAPI: Exception while fetching external quote status for {{external_quote_id}}: {{e}}", exc_info=True)
            return None

    def update_quote_in_external_system(self, external_quote_id: str, update_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Updates an existing quote in the external John Deere system.

        Args:
            external_quote_id (str): The ID of the quote to update.
            update_payload (Dict[str, Any]): The data to update the quote with.

        Returns:
            Optional[Dict[str, Any]]: The response from the external system, or None on failure.
        """
        if not self.is_operational:
            logger.error("MaintainQuotesAPI: Cannot update quote. Service is not operational.")
            return None

        if not self.jd_quote_api_client:
            logger.error("MaintainQuotesAPI: JDQuoteApiClient not available. Cannot update quote.")
            return None

        logger.info(f"MaintainQuotesAPI: Attempting to update quote {external_quote_id} in external system with payload: {update_payload}")
        try:
            response = self.jd_quote_api_client.update_existing_quote(quote_id=external_quote_id, update_data=update_payload)
            if response and response.get("status") == "updated": # Assuming a successful update response structure
                logger.info(f"MaintainQuotesAPI: Quote {external_quote_id} successfully updated in external system.")
                return response
            else:
                logger.error(f"MaintainQuotesAPI: Failed to update quote {external_quote_id} or received unexpected response: {response}")
                return None
        except Exception as e:
            logger.error(f"MaintainQuotesAPI: Exception during external quote update for {external_quote_id}: {e}", exc_info=True)
            return None


# Example Usage (for testing this module standalone)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    # Simulate Config object
    class MockConfigMaintain(Config):
        def __init__(self, settings_dict=None):
            self.settings = settings_dict if settings_dict else {}
            # Minimal super init for Config's structure if its methods are called
            super().__init__(env_path=".env.test_maintain_api")
            if settings_dict: self.settings.update(settings_dict)


    # Simulate JDQuoteApiClient
    class MockJDQuoteApiClient:
        def __init__(self, operational=True, base_url="http://mock.api"):
            self.is_operational = operational
            self.base_url = base_url
            self.logger = logging.getLogger("MockJDQuoteApiClient")

        def submit_new_quote(self, quote_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            self.logger.info(f"MockJDQuoteApiClient: submit_new_quote called with {quote_data}")
            if not self.is_operational: return None
            return {"id": "MOCK_NEW_QUOTE_ID_123", "status": "submitted", "message": "Quote created in mock client"}

        def get_quote_details(self, quote_id: str) -> Optional[Dict[str, Any]]:
            self.logger.info(f"MockJDQuoteApiClient: get_quote_details called for {quote_id}")
            if not self.is_operational: return None
            return {"id": quote_id, "status": "approved", "amount": 5000, "customer": "Mock Customer Inc."}

        def update_existing_quote(self, quote_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            self.logger.info(f"MockJDQuoteApiClient: update_existing_quote called for {quote_id} with {update_data}")
            if not self.is_operational: return None
            return {"id": quote_id, "status": "updated", "message": "Quote updated in mock client"}


    mock_config_instance = MockConfigMaintain()

    # --- Test Case 1: MaintainQuotesAPI Operational ---
    print("\n--- Test Case 1: MaintainQuotesAPI Operational ---")
    mock_jd_client_ok = MockJDQuoteApiClient(operational=True)
    maintain_api_ok = MaintainQuotesAPI(config=mock_config_instance, jd_quote_api_client=mock_jd_client_ok)
    print(f"MaintainQuotesAPI Operational: {maintain_api_ok.is_operational}")

    if maintain_api_ok.is_operational:
        creation_response = maintain_api_ok.create_quote_in_external_system({"item": "Tractor X100", "price": 75000})
        print(f"Create Quote Response: {creation_response}")

        if creation_response and creation_response.get("id"):
            status_response = maintain_api_ok.get_external_quote_status(creation_response.get("id"))
            print(f"Get Quote Status Response: {status_response}")

            update_response = maintain_api_ok.update_quote_in_external_system(creation_response.get("id"), {"price": 72000, "notes": "Special discount applied"})
            print(f"Update Quote Response: {update_response}")


    # --- Test Case 2: MaintainQuotesAPI Not Operational (JDQuoteApiClient not operational) ---
    print("\n--- Test Case 2: MaintainQuotesAPI Not Operational (JDQuoteApiClient not op) ---")
    mock_jd_client_not_op = MockJDQuoteApiClient(operational=False)
    maintain_api_not_op_client = MaintainQuotesAPI(config=mock_config_instance, jd_quote_api_client=mock_jd_client_not_op)
    print(f"MaintainQuotesAPI Operational: {maintain_api_not_op_client.is_operational}")
    creation_response_fail = maintain_api_not_op_client.create_quote_in_external_system({"item": "Plow Y200", "price": 5000})
    print(f"Create Quote Response (should be None or error): {creation_response_fail}")

    # --- Test Case 3: MaintainQuotesAPI Not Operational (JDQuoteApiClient not provided) ---
    print("\n--- Test Case 3: MaintainQuotesAPI Not Operational (JDQuoteApiClient not provided) ---")
    maintain_api_no_client = MaintainQuotesAPI(config=mock_config_instance, jd_quote_api_client=None)
    print(f"MaintainQuotesAPI Operational: {maintain_api_no_client.is_operational}")
    status_response_fail = maintain_api_no_client.get_external_quote_status("ANY_ID")
    print(f"Get Quote Status Response (should be None or error): {status_response_fail}")

    # Clean up dummy .env file if created by MockConfigMaintain's super().__init__
    if os.path.exists(".env.test_maintain_api"):
        os.remove(".env.test_maintain_api")
