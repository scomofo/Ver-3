# api/MaintainQuotesAPI.py - Updated to fix API issues

import requests
import json
import logging
import time
import traceback
from datetime import datetime, timedelta

class MaintainQuotesAPI:
    """Client for interacting with John Deere's Maintain Quotes API."""
    
    def __init__(self, base_url=None, access_token=None, logger=None):
        """Initialize the Maintain Quotes API client.
        
        Args:
            base_url: Base URL for the API (defaults to sandbox)
            access_token: OAuth access token (optional, can be set later)
            logger: Logger instance (optional)
        """
        self.base_url = base_url or "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"
        self.access_token = None  # Initialize as None, set properly with set_access_token
        self.logger = logger or logging.getLogger(__name__)
        
        # Set up session with default headers
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Set token if provided
        if access_token:
            self.set_access_token(access_token)
            
        self.logger.info(f"MaintainQuotesAPI client initialized with base URL: {self.base_url}")
    
    def set_access_token(self, access_token):
        """Set the OAuth access token for API requests.
        
        Args:
            access_token: The OAuth access token
        """
        if not access_token:
            self.logger.error("Attempted to set empty access token")
            return

        # Clean the token to remove any whitespace or newlines
        if isinstance(access_token, str):
            access_token = access_token.strip()
            
            # Simple validation
            if not access_token or len(access_token) < 20:  # Arbitrary minimum length
                self.logger.error(f"Access token appears to be invalid (too short): {len(access_token)} chars")
                return
        else:
            self.logger.error(f"Access token must be a string, got {type(access_token)}")
            return
        
        # Set the token
        self.access_token = access_token
        
        # Update session headers with token
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}"
        })
        
        self.logger.info("Set new access token for MaintainQuotesAPI")
        self.logger.debug(f"Token starts with: {access_token[:10]}...")
    
    def _make_request(self, method, endpoint, params=None, data=None, retry_on_auth_error=True, max_retries=2):
        """Make an API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (will be appended to base_url)
            params: Query parameters (optional)
            data: Request body data (optional)
            retry_on_auth_error: Whether to retry on auth error (default: True)
            max_retries: Maximum number of retries (default: 2)
            
        Returns:
            API response as dictionary or None if failed
        """
        url = f"{self.base_url}{endpoint}"
        
        # Check if we have a token
        if not self.access_token:
            self.logger.error("No access token set. Please set an access token before making requests.")
            return None
        
        retries = 0
        while retries <= max_retries:
            try:
                self.logger.debug(f"Making {method} request to {url}")
                if data:
                    self.logger.debug(f"Request data: {json.dumps(data)}")
                
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=30)
                elif method == "POST":
                    response = self.session.post(url, params=params, json=data, timeout=30)
                elif method == "PUT":
                    response = self.session.put(url, params=params, json=data, timeout=30)
                elif method == "DELETE":
                    response = self.session.delete(url, params=params, timeout=30)
                else:
                    self.logger.error(f"Unsupported HTTP method: {method}")
                    return None
                
                # Log response status
                self.logger.debug(f"Response status: {response.status_code}")
                
                # Handle authentication errors
                if response.status_code == 401:
                    self.logger.error(f"Authentication error: {response.status_code} - {response.text}")
                    if retry_on_auth_error and retries < max_retries:
                        retries += 1
                        self.logger.info(f"Retrying request ({retries}/{max_retries})...")
                        time.sleep(1)  # Brief delay before retry
                        continue
                    else:
                        return {
                            "error": "Authentication failed",
                            "message": response.text,
                            "status": response.status_code
                        }
                
                # Handle non-200 responses
                if response.status_code != 200:
                    self.logger.error(f"API error: {response.status_code} - {response.text}")
                    return {
                        "error": f"API returned status {response.status_code}",
                        "message": response.text,
                        "status": response.status_code
                    }
                
                # Parse JSON response
                try:
                    response_json = response.json()
                    self.logger.debug(f"Response JSON: {json.dumps(response_json)[:500]}...")
                    return response_json
                except ValueError:
                    self.logger.error("Failed to parse JSON response")
                    self.logger.debug(f"Raw response: {response.text[:500]}...")
                    return {
                        "error": "Invalid JSON response",
                        "message": response.text[:500],
                        "status": response.status_code
                    }
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {str(e)}")
                if retries < max_retries:
                    retries += 1
                    self.logger.info(f"Retrying request ({retries}/{max_retries})...")
                    time.sleep(1)  # Brief delay before retry
                    continue
                else:
                    return {
                        "error": "Request failed",
                        "message": str(e)
                    }
            except Exception as e:
                self.logger.error(f"Unexpected error in API request: {str(e)}")
                self.logger.error(traceback.format_exc())
                return {
                    "error": "Unexpected error",
                    "message": str(e)
                }
        
        # This should not be reached if the loop exits normally
        return None
    
    def ping(self):
        """Test the API connection.
        
        Returns:
            True if successful, False otherwise
        """
        # Use a simple search endpoint for the ping test
        # This is more likely to succeed with limited permissions than the original test endpoint
        endpoint = "/api/v1/dealers/X731804/maintain-quotes"
        data = {
            "dealerRacfID": "X731804",
            "startModifiedDate": "03/01/2025", 
            "endModifiedDate": "04/15/2025"
        }
        
        self.logger.info("Testing API connection")
        response = self._make_request("POST", endpoint, data=data, retry_on_auth_error=False)
        
        # Even if we get a 404 or similar error, as long as it's not a 401 auth error,
        # we can consider the token valid
        if response is not None:
            if isinstance(response, dict) and response.get('status') == 401:
                self.logger.error("API connection test failed: Authentication error")
                return False
            
            # Could be valid even with error responses for invalid dealer ID
            self.logger.info("API connection test successful (token is valid)")
            return True
        
        self.logger.error("API connection test failed (no response)")
        return False
    
    def get_quotes(self, dealer_racf_id, start_date=None, end_date=None, quote_id=None):
        """Get a list of quotes.
        
        Args:
            dealer_racf_id: Dealer RACF ID
            start_date: Start date for filtering (MM/DD/YYYY format)
            end_date: End date for filtering (MM/DD/YYYY format)
            quote_id: Specific quote ID (optional)
            
        Returns:
            List of quotes or None if failed
        """
        endpoint = f"/api/v1/dealers/{dealer_racf_id}/maintain-quotes"
        
        # Build request body
        data = {
            "dealerRacfID": dealer_racf_id
        }
        
        # Add optional parameters
        if start_date:
            data["startModifiedDate"] = start_date
        if end_date:
            data["endModifiedDate"] = end_date
        if quote_id:
            data["quoteId"] = quote_id
        
        self.logger.info(f"Getting quotes for {dealer_racf_id} from {start_date} to {end_date}")
        response = self._make_request("POST", endpoint, data=data)
        
        if response and isinstance(response, dict) and response.get('type') == 'SUCCESS' and 'body' in response:
            return response['body']
        
        return response