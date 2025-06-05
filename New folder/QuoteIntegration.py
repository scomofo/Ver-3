# api/QuoteIntegration.py - Updated to fix integration issues

import logging
import os
import json
import time
import traceback
from datetime import datetime, timedelta

class QuoteIntegration:
    """Integration with John Deere Quotes API."""
    
    def __init__(self, quotes_api=None, sharepoint_manager=None, logger=None, config=None):
        """Initialize the quote integration.
        
        Args:
            quotes_api: MaintainQuotesAPI instance
            sharepoint_manager: SharePoint manager instance
            logger: Logger instance
            config: Configuration instance
        """
        self.api = quotes_api
        self.sharepoint_manager = sharepoint_manager
        self.logger = logger or logging.getLogger(__name__)
        self.config = config
        
        # Default dealer ID from environment or hardcode for testing
        # Based on API docs, dealer ID format should be like "X731804"
        self.dealer_id = os.getenv('DEFAULT_DEALER_ID', 'X731804')
        # Ensure dealer_id is in proper format (starts with X)
        if not str(self.dealer_id).startswith('X') and str(self.dealer_id).isdigit():
            self.dealer_id = f"X{self.dealer_id}"
            
        self.dealer_account_no = os.getenv('DEALER_NUMBER', '731804')
        
        # Try to load token if we have the API but no token
        if self.api and (not hasattr(self.api, 'access_token') or not self.api.access_token) and config:
            self._load_cached_token()
            
        self.logger.info(f"QuoteIntegration initialized with dealer: {self.dealer_id}, account: {self.dealer_account_no}")
    
    def _load_cached_token(self):
        """Load a cached OAuth token if available."""
        if not self.config or not hasattr(self.config, 'cache_path'):
            self.logger.warning("Cannot load cached token: config or cache_path not available")
            return
            
        token_path = os.path.join(self.config.cache_path, "jd_token.json")
        try:
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    token_data = json.load(f)
                    # Check if token is still valid (has some time left before expiry)
                    if 'expires_at' in token_data and token_data['expires_at'] > time.time() + 300:  # 5 min buffer
                        self.logger.info("Using cached JD OAuth token")
                        if self.api:
                            self.api.set_access_token(token_data['access_token'])
                            return True
            
            self.logger.info("No valid cached token found")
            return False
        except Exception as e:
            self.logger.error(f"Error loading cached token: {str(e)}")
            return False
    
    def set_dealer(self, dealer_id):
        """Set the dealer ID for API calls.
        
        Args:
            dealer_id: Dealer RACF ID
        """
        self.dealer_id = dealer_id
        # Ensure dealer_id is in proper format (starts with X)
        if not str(self.dealer_id).startswith('X') and str(self.dealer_id).isdigit():
            self.dealer_id = f"X{self.dealer_id}"
        self.logger.info(f"Dealer ID set to: {self.dealer_id}")
    
    def ensure_token(self):
        """Ensure we have a valid token, prompting for one if needed."""
        # Check if token exists
        token_valid = False
        
        if self.api and hasattr(self.api, 'access_token') and self.api.access_token:
            # Assume token is valid initially - we'll verify on first use
            token_valid = True
            
        if not token_valid:
            # No API, no token, or invalid token - we need to get a new one
            if hasattr(self, 'logger'):
                self.logger.info("No valid OAuth token available, requesting one")
                
            # Check if we're running in a GUI context
            try:
                from PyQt5.QtWidgets import QApplication, QInputDialog, QLineEdit
                if QApplication.instance():
                    token, ok = QInputDialog.getText(
                        None,  # No parent widget, will be centered on screen
                        "John Deere API Authentication",
                        "Enter your OAuth access token for John Deere Quotes API:",
                        QLineEdit.Normal
                    )
                    
                    if ok and token:
                        # Set token in API
                        if self.api:
                            self.api.set_access_token(token)
                        
                        # Save token for future use if we have config
                        if hasattr(self, 'config') and self.config and hasattr(self.config, 'cache_path'):
                            token_path = os.path.join(self.config.cache_path, "jd_token.json")
                            token_data = {
                                'access_token': token,
                                'expires_in': 43200,  # 12 hours
                                'expires_at': time.time() + 43200  # 12 hours
                            }
                            try:
                                os.makedirs(os.path.dirname(token_path), exist_ok=True)
                                with open(token_path, 'w') as f:
                                    json.dump(token_data, f)
                                if hasattr(self, 'logger'):
                                    self.logger.info("Saved new JD OAuth token")
                            except Exception as e:
                                if hasattr(self, 'logger'):
                                    self.logger.error(f"Error saving token: {str(e)}")
                        
                        return True
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(f"Error showing token dialog: {str(e)}")
                    
            return False
        return True
    
    def get_dealer_quotes(self, dealer_racf_id=None, start_date=None, end_date=None, quote_id=None):
        """Get quotes for a specific dealer.
        
        Args:
            dealer_racf_id: Dealer RACF ID (optional, uses self.dealer_id if not provided)
            start_date: Start date in MM/dd/yyyy format
            end_date: End date in MM/dd/yyyy format
            quote_id: Optional quote ID to filter
            
        Returns:
            List of quotes or empty list if failed
        """
        if not self.api:
            if hasattr(self, 'logger'):
                self.logger.error("API not initialized")
            return []
        
        # Ensure we have a token
        if not self.ensure_token():
            if hasattr(self, 'logger'):
                self.logger.error("Failed to get OAuth token")
            return []
        
        # Use provided dealer_racf_id or fall back to the default one
        dealer_id = dealer_racf_id if dealer_racf_id is not None else self.dealer_id
        
        # If dealer_id doesn't start with 'X', ensure it's prefixed as per API docs
        if not str(dealer_id).startswith('X') and str(dealer_id).isdigit():
            dealer_id = f"X{dealer_id}"
            if hasattr(self, 'logger'):
                self.logger.info(f"Converted dealer ID to RACF format: {dealer_id}")
        
        # Log the parameters for debugging
        if hasattr(self, 'logger'):
            self.logger.info(f"Getting quotes with: dealer_id={dealer_id}, start={start_date}, end={end_date}")
        
        try:
            response = self.api.get_quotes(dealer_id, start_date, end_date, quote_id)
            
            # Log the raw response for debugging
            if hasattr(self, 'logger'):
                self.logger.info(f"Raw API response type: {type(response)}")
                if response is None:
                    self.logger.error("API returned None response")
                    return []
                elif isinstance(response, dict):
                    if 'error' in response:
                        self.logger.error(f"API error: {response['error']}")
                        return []
                    
                    # Most likely format: {'type': 'SUCCESS', 'body': [...]}
                    if 'type' in response and 'body' in response:
                        if response['type'] == 'SUCCESS' and isinstance(response['body'], list):
                            self.logger.info(f"Successfully retrieved {len(response['body'])} quotes")
                            return response['body']
                        else:
                            self.logger.error(f"Unexpected response format: {response['type']}")
                            # Try to handle body as list even if not 'SUCCESS'
                            if isinstance(response['body'], list):
                                return response['body']
                            return []
                    
                    self.logger.error(f"Unexpected response format: missing 'type' or 'body'")
                    return []
                elif isinstance(response, list):
                    # Direct list response
                    self.logger.info(f"Got direct list response with {len(response)} quotes")
                    return response
                        
            # If we got here without returning, try a naive extraction
            if response and isinstance(response, dict) and 'body' in response:
                body = response['body']
                if isinstance(body, list):
                    return body
                elif isinstance(body, str):
                    # Try to parse as JSON if it's a string
                    try:
                        parsed_body = json.loads(body)
                        if isinstance(parsed_body, list):
                            return parsed_body
                    except json.JSONDecodeError:
                        pass
            elif isinstance(response, list):
                # Direct list response
                return response
            
            # If all else fails, return empty list
            return []
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error getting dealer quotes: {str(e)}")
                self.logger.error(traceback.format_exc())
            return []