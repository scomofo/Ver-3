# app/services/integrations/jd_quote_integration_service.py
import logging
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# Assuming Config class is in app.core.config
from app.core.config import BRIDealConfig, get_config
# Assuming MaintainQuotesAPI is used for interacting with the JD system via an API client
from app.services.api_clients.maintain_quotes_api import MaintainQuotesAPI
# Assuming QuoteBuilder is a local utility for formatting quote data
from app.services.api_clients.quote_builder import QuoteBuilder # Or wherever it's located

logger = logging.getLogger(__name__)

# Configuration key for the path to a specific JD Quote App config file (e.g., for the Tkinter app)
CONFIG_KEY_JD_QUOTE_APP_CONFIG_FILE_PATH = "JD_QUOTE_APP_CONFIG_FILE_PATH" # Example name

class JDQuoteIntegrationService:
    """
    Service to integrate John Deere quoting functionalities.
    It uses MaintainQuotesAPI for external system interactions and QuoteBuilder for payload preparation.
    It can also manage configurations for an external JD Quote App (e.g., a Tkinter tool).
    """
    def __init__(self,
                 config: BRIDealConfig,
                 maintain_quotes_api: Optional[MaintainQuotesAPI] = None,
                 quote_builder: Optional[QuoteBuilder] = None):
        """
        Initializes the JDQuoteIntegrationService.

        Args:
            config (Config): The application's configuration object.
            maintain_quotes_api (Optional[MaintainQuotesAPI]): API service for maintaining quotes in JD system.
            quote_builder (Optional[QuoteBuilder]): Utility to build quote payloads.
        """
        self.config = config
        self.maintain_quotes_api = maintain_quotes_api
        self.quote_builder = quote_builder
        self.is_operational: bool = False
        self.jd_quote_app_specific_config: Dict[str, Any] = {} # For external Tkinter app config

        if not self.config:
            logger.error("JDQuoteIntegrationService: BRIDealConfig object not provided. Service will be non-functional.")
            return # Cannot proceed without config

        if not self.quote_builder:
            logger.warning("JDQuoteIntegrationService: QuoteBuilder not provided. Payload preparation might be limited.")
            # Depending on how critical QuoteBuilder is, you might set self.is_operational = False here
            # For now, let's assume it can operate without it for some tasks, or it's always provided.

        # Load specific configuration for the JD Quote App (e.g., Tkinter tool)
        self._load_jd_quote_app_config() # This was mentioned in original logs

        # The service is operational if its core dependency (MaintainQuotesAPI) is operational.
        if self.maintain_quotes_api:
            if self.maintain_quotes_api.is_operational:
                self.is_operational = True
                logger.info("JDQuoteIntegrationService initialized and operational (MaintainQuotesAPI is available and operational).")
            else:
                logger.warning("JDQuoteIntegrationService: MaintainQuotesAPI is provided but not operational. Service will have limited or no functionality for external JD system interaction.")
        else:
            logger.warning("JDQuoteIntegrationService: MaintainQuotesAPI is not provided. Service cannot interact with external JD system.")
            # self.is_operational remains False

    def _handle_api_response(self, response, operation_name):
        """
        Handle API responses in a standard way.
        
        Args:
            response: The response from the API
            operation_name: Name of the operation for logging purposes
            
        Returns:
            dict: A standardized response object with type and body
        """
        if response is None:
            logger.error(f"No response received from {operation_name} operation")
            return {
                "type": "ERROR",
                "body": {"errorMessage": f"No response received from {operation_name} operation"}
            }
        
        if isinstance(response, dict) and response.get("error"):
            logger.error(f"Error in {operation_name} operation: {response.get('error')}")
            return {
                "type": "ERROR",
                "body": {"errorMessage": response.get("error")}
            }
        
        # If the response already has the expected structure, return it
        if isinstance(response, dict) and "type" in response and "body" in response:
            return response
        
        # Otherwise, wrap the response in the expected structure
        logger.info(f"Successful {operation_name} operation")
        return {
            "type": "SUCCESS",
            "body": response
        }

    def _load_jd_quote_app_config(self):
        """
        Loads specific configuration for the JD Quote App if a path is provided in the main config.
        This is relevant if an external tool (like a Tkinter app) needs its own settings.
        """
        if not self.config: return

        config_file_path = self.config.get(CONFIG_KEY_JD_QUOTE_APP_CONFIG_FILE_PATH) # e.g., "jd_quote_app_settings.json"

        if config_file_path and os.path.exists(config_file_path):
            try:
                with open(config_file_path, 'r') as f:
                    self.jd_quote_app_specific_config = json.load(f)
                logger.info(f"JDQuoteIntegrationService: Successfully loaded JD Quote App specific config from {config_file_path}")
            except json.JSONDecodeError:
                logger.error(f"JDQuoteIntegrationService: Error decoding JSON from JD Quote App config file: {config_file_path}", exc_info=True)
                self.jd_quote_app_specific_config = {} # Use empty config on error
            except Exception as e:
                logger.error(f"JDQuoteIntegrationService: An unexpected error occurred while reading JD Quote App config file {config_file_path}: {e}", exc_info=True)
                self.jd_quote_app_specific_config = {}
        elif config_file_path:
            logger.warning(f"JDQuoteIntegrationService: JD Quote App specific config file not found at '{config_file_path}'. Using empty config.")
            self.jd_quote_app_specific_config = {}
        else:
            # This matches the original log warning if the path itself isn't configured
            logger.debug("JDQuoteIntegrationService: Path for JD Quote App specific config file not configured. Using empty config.")
            self.jd_quote_app_specific_config = {}


    def prepare_quote_payload_for_external_app(self, deal_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Prepares a quote payload suitable for an external application (e.g., the Tkinter JD Quote App)
        or for submission to the John Deere API via MaintainQuotesAPI.

        Args:
            deal_data (Dict[str, Any]): The internal deal data from BRIDeal.

        Returns:
            Optional[Dict[str, Any]]: The prepared quote payload, or None on failure.
        """
        if not self.quote_builder:
            logger.error("JDQuoteIntegrationService: QuoteBuilder not available. Cannot prepare quote payload.")
            return None

        logger.info(f"JDQuoteIntegrationService: Preparing quote payload for deal ID: {deal_data.get('deal_id', 'N/A')}")
        try:
            # Use QuoteBuilder to transform deal_data into the required format
            # The QuoteBuilder might need access to jd_quote_app_specific_config if the format depends on it
            prepared_payload = self.quote_builder.build_payload_from_deal(
                deal_data,
                target_system="jd_api" # Or "jd_tkinter_app" if format differs
                # You might pass self.jd_quote_app_specific_config to quote_builder if needed
            )
            if prepared_payload:
                logger.info("JDQuoteIntegrationService: Quote payload prepared successfully.")
                return prepared_payload
            else:
                logger.error("JDQuoteIntegrationService: QuoteBuilder returned an empty payload.")
                return None
        except Exception as e:
            logger.error(f"JDQuoteIntegrationService: Exception during quote payload preparation: {e}", exc_info=True)
            return None

    def submit_prepared_quote(self, prepared_quote_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Submits a prepared quote payload to the John Deere system via MaintainQuotesAPI.

        Args:
            prepared_quote_payload (Dict[str, Any]): The quote payload, typically from prepare_quote_payload.

        Returns:
            Optional[Dict[str, Any]]: The response from the JD system, or None on failure.
        """
        if not self.is_operational:
            logger.error("JDQuoteIntegrationService: Cannot submit quote. Service is not operational (MaintainQuotesAPI issue).")
            return None # Or raise an exception

        if not self.maintain_quotes_api: # Should be caught by is_operational
            logger.error("JDQuoteIntegrationService: MaintainQuotesAPI not available. Cannot submit quote.")
            return None

        logger.info("JDQuoteIntegrationService: Submitting prepared quote to external JD system.")
        try:
            response = self.maintain_quotes_api.create_quote_in_external_system(quote_payload=prepared_quote_payload)
            # MaintainQuotesAPI's method already logs success/failure details
            return response
        except Exception as e:
            # This is a fallback catch, MaintainQuotesAPI should handle its own exceptions primarily
            logger.error(f"JDQuoteIntegrationService: Unexpected exception during quote submission: {e}", exc_info=True)
            return None

    def get_quote_status_from_external_system(self, external_quote_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the status of a quote from the John Deere system.
        """
        if not self.is_operational:
            logger.error("JDQuoteIntegrationService: Cannot get quote status. Service is not operational.")
            return None
        if not self.maintain_quotes_api:
            logger.error("JDQuoteIntegrationService: MaintainQuotesAPI not available. Cannot get quote status.")
            return None

        return self.maintain_quotes_api.get_external_quote_status(external_quote_id)

    def create_quote_via_api(self, quote_payload: dict) -> dict:
        """
        Creates a quote in the John Deere system via API.
        
        Args:
            quote_payload (dict): The structured payload for the quote API
            
        Returns:
            dict: The API response containing the quoteID if successful
        """
        try:
            # Make the POST request using maintain_quotes_api
            response = self.maintain_quotes_api.post('/api/v1/maintain-quotes', data=quote_payload)
            
            # Use the standard response handler
            handled_response = self._handle_api_response(response, "create quote")
            
            # Log success info
            if handled_response.get("type") == "SUCCESS" and handled_response.get("body", {}).get("quoteID"):
                quote_id = handled_response.get("body", {}).get("quoteID")
                logger.info(f"Successfully created quote in John Deere system. Quote ID: {quote_id}")
                
            return handled_response
        except Exception as e:
            logger.error(f"Error creating quote via API: {e}", exc_info=True)
            return {"type": "ERROR", "body": {"errorMessage": str(e)}}

    def get_quote_details_via_api(self, quote_id: str, dealer_account_no: str) -> dict:
        """
        Retrieves quote details from the John Deere system.
        
        Args:
            quote_id (str): The ID of the quote to retrieve
            dealer_account_no (str): The dealer's account number
            
        Returns:
            dict: The API response containing the quote details
        """
        try:
            if not self.is_operational:
                logger.error("JDQuoteIntegrationService: Cannot get quote details. Service is not operational.")
                return {"type": "ERROR", "body": {"errorMessage": "Service is not operational"}}
            
            if not self.maintain_quotes_api:
                logger.error("JDQuoteIntegrationService: MaintainQuotesAPI not available. Cannot get quote details.")
                return {"type": "ERROR", "body": {"errorMessage": "MaintainQuotesAPI not available"}}
            
            logger.info(f"Requesting quote details for quote ID: {quote_id}")
            # Use the get_external_quote_status method which is already implemented in MaintainQuotesAPI
            response = self.maintain_quotes_api.get_external_quote_status(quote_id)
            
            # Use the standard response handler
            handled_response = self._handle_api_response(response, f"retrieve quote details for {quote_id}")
            
            # Add dealer account number to the response if needed
            if handled_response.get("type") == "SUCCESS" and isinstance(handled_response.get("body"), dict):
                if 'dealerAccountNo' not in handled_response["body"]:
                    handled_response["body"]['dealerAccountNo'] = dealer_account_no
            
            return handled_response
                
        except Exception as e:
            logger.error(f"Error retrieving quote details via API: {e}", exc_info=True)
            return {"type": "ERROR", "body": {"errorMessage": str(e)}}


# Example Usage (for testing this module standalone)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    # Simulate Config object
    class MockConfigIntegration(Config):
        def __init__(self, settings_dict=None, jd_quote_app_config_path=None):
            self.settings = settings_dict if settings_dict else {}
            if jd_quote_app_config_path:
                self.settings[CONFIG_KEY_JD_QUOTE_APP_CONFIG_FILE_PATH] = jd_quote_app_config_path
            super().__init__(env_path=".env.test_jd_integration") # Dummy path for super init
            if settings_dict: self.settings.update(settings_dict)


    # Simulate MaintainQuotesAPI
    class MockMaintainQuotesAPI:
        def __init__(self, operational=True):
            self.is_operational = operational
            self.logger = logging.getLogger("MockMaintainQuotesAPI")

        def create_quote_in_external_system(self, quote_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            self.logger.info(f"MockMaintainQuotesAPI: create_quote_in_external_system called with {quote_payload}")
            if not self.is_operational: return None
            return {"id": "EXT_SYS_QUOTE_789", "status": "pending_approval", "message": "Quote created in mock external system"}

        def get_external_quote_status(self, external_quote_id: str) -> Optional[Dict[str, Any]]:
            self.logger.info(f"MockMaintainQuotesAPI: get_external_quote_status for {external_quote_id}")
            if not self.is_operational: return None
            return {"id": external_quote_id, "status": "approved", "details": "All good"}

    # Simulate QuoteBuilder
    class MockQuoteBuilder:
        def __init__(self):
            self.logger = logging.getLogger("MockQuoteBuilder")

        def build_payload_from_deal(self, deal_data: Dict[str, Any], target_system: str) -> Optional[Dict[str, Any]]:
            self.logger.info(f"MockQuoteBuilder: build_payload_from_deal for {deal_data.get('deal_id')} targeting {target_system}")
            return {"prepared_customer_name": deal_data.get("customer", {}).get("name"), "total_value": deal_data.get("financials",{}).get("grand_total", 0)}

    mock_config_instance = MockConfigIntegration()
    mock_quote_builder_instance = MockQuoteBuilder()

    # --- Test Case 1: Service Operational ---
    print("\n--- Test Case 1: Service Operational ---")
    mock_maintain_api_ok = MockMaintainQuotesAPI(operational=True)
    integration_service_ok = JDQuoteIntegrationService(
        config=mock_config_instance,
        maintain_quotes_api=mock_maintain_api_ok,
        quote_builder=mock_quote_builder_instance
    )
    print(f"Integration Service Operational: {integration_service_ok.is_operational}")

    if integration_service_ok.is_operational:
        sample_deal_data = {
            "deal_id": "DEAL-001",
            "customer": {"name": "Test Customer"},
            "financials": {"grand_total": 12000}
        }
        prepared_payload = integration_service_ok.prepare_quote_payload_for_external_app(sample_deal_data)
        print(f"Prepared Payload: {prepared_payload}")

        if prepared_payload:
            submission_response = integration_service_ok.submit_prepared_quote(prepared_payload)
            print(f"Submission Response: {submission_response}")
            if submission_response and submission_response.get("id"):
                status = integration_service_ok.get_quote_status_from_external_system(submission_response.get("id"))
                print(f"Status check for {submission_response.get('id')}: {status}")


    # --- Test Case 2: Service Not Operational (MaintainQuotesAPI not operational) ---
    print("\n--- Test Case 2: Service Not Operational (MaintainQuotesAPI not op) ---")
    mock_maintain_api_not_op = MockMaintainQuotesAPI(operational=False)
    integration_service_not_op_maintain = JDQuoteIntegrationService(
        config=mock_config_instance,
        maintain_quotes_api=mock_maintain_api_not_op,
        quote_builder=mock_quote_builder_instance
    )
    print(f"Integration Service Operational: {integration_service_not_op_maintain.is_operational}")
    submission_response_fail = integration_service_not_op_maintain.submit_prepared_quote({"data": "some_payload"})
    print(f"Submission Response (should be None or error): {submission_response_fail}")


    # --- Test Case 3: Service Not Operational (MaintainQuotesAPI not provided) ---
    print("\n--- Test Case 3: Service Not Operational (MaintainQuotesAPI not provided) ---")
    integration_service_no_maintain = JDQuoteIntegrationService(
        config=mock_config_instance,
        maintain_quotes_api=None, # Not provided
        quote_builder=mock_quote_builder_instance
    )
    print(f"Integration Service Operational: {integration_service_no_maintain.is_operational}")


    # --- Test Case 4: Loading JD Quote App Specific Config ---
    print("\n--- Test Case 4: Loading JD Quote App Specific Config ---")
    dummy_jd_app_config_content = {"theme": "dark", "default_user": "jd_user"}
    dummy_jd_app_config_filename = "temp_jd_app_config.json"
    with open(dummy_jd_app_config_filename, 'w') as f:
        json.dump(dummy_jd_app_config_content, f)

    mock_config_with_app_path = MockConfigIntegration(jd_quote_app_config_path=dummy_jd_app_config_filename)
    integration_service_with_app_config = JDQuoteIntegrationService(
        config=mock_config_with_app_path,
        maintain_quotes_api=mock_maintain_api_ok, # Assuming this is operational
        quote_builder=mock_quote_builder_instance
    )
    print(f"Loaded JD App Specific Config: {integration_service_with_app_config.jd_quote_app_specific_config}")
    if os.path.exists(dummy_jd_app_config_filename):
        os.remove(dummy_jd_app_config_filename)


    # Clean up dummy .env file if created by MockConfigIntegration's super().__init__
    if os.path.exists(".env.test_jd_integration"):
        os.remove(".env.test_jd_integration")
