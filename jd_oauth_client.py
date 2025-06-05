import os
import json
import time
import requests
import logging
import base64

# Set up logging
logger = logging.getLogger('JDQuoteApp.OAuth')

class JDOAuthClient:
    """OAuth client for John Deere API authentication."""
    
    def __init__(self, client_id, client_secret, token_url=None, token_cache_path=None):
        """
        Initialize the OAuth client
        
        Args:
            client_id (str): Client ID
            client_secret (str): Client Secret
            token_url (str, optional): Token endpoint URL
            token_cache_path (str, optional): Path to token cache file
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url or "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"
        self.token_cache_path = token_cache_path or os.path.join(os.path.expanduser("~"), ".jd_quote_app", "token_cache.json")
        self.token_data = None
        
        # Create cache directory if it doesn't exist
        os.makedirs(os.path.dirname(self.token_cache_path), exist_ok=True)
        
        # Try to load token from cache
        self._load_token_from_cache()
        
        logger.info(f"OAuth client initialized with client ID: {client_id[:4]}...")
    
    def _load_token_from_cache(self):
        """Load token from cache file if it exists."""
        if os.path.exists(self.token_cache_path):
            try:
                with open(self.token_cache_path, 'r') as f:
                    self.token_data = json.load(f)
                
                # Check if token is expired or about to expire (within 5 minutes)
                if self._is_token_valid():
                    logger.info("Loaded valid token from cache")
                else:
                    logger.info("Cached token is expired, will need to refresh")
                    # We'll try to refresh the token when get_auth_header is called
            except Exception as e:
                logger.error(f"Error loading token from cache: {str(e)}")
                self.token_data = None
    
    def _save_token_to_cache(self):
        """Save token to cache file."""
        try:
            with open(self.token_cache_path, 'w') as f:
                json.dump(self.token_data, f)
            logger.debug("Saved token to cache")
        except Exception as e:
            logger.error(f"Error saving token to cache: {str(e)}")
    
    def _is_token_valid(self):
        """Check if the current token is valid and not expired."""
        if not self.token_data or 'expires_at' not in self.token_data:
            return False
        
        # Check if token is expired or about to expire (within 5 minutes)
        current_time = time.time()
        expires_at = self.token_data['expires_at']
        
        # If token expires in less than 5 minutes, consider it invalid
        return expires_at > current_time + 300
    
    def _get_new_token(self):
        """Get a new token using client credentials flow."""
        logger.info("Getting new token")
        
        try:
            # Prepare the request
            auth_string = f"{self.client_id}:{self.client_secret}"
            encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "client_credentials",
                "scope": "offline_access axiom"
            }
            
            # Make the request
            response = requests.post(self.token_url, headers=headers, data=data)
            
            # Check for errors
            if response.status_code != 200:
                logger.error(f"Token request failed: {response.status_code} - {response.text}")
                raise Exception(f"Token request failed: {response.status_code} - {response.text}")
            
            # Parse the response
            token_data = response.json()
            
            # Add expiration time
            token_data['expires_at'] = time.time() + token_data.get('expires_in', 3600)
            
            # Store the token
            self.token_data = token_data
            
            # Save to cache
            self._save_token_to_cache()
            
            logger.info("Successfully obtained new token")
            return token_data
        
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            raise Exception(f"Error getting token: {str(e)}")
    
    def _refresh_token(self):
        """Refresh the token using the refresh token."""
        logger.info("Refreshing token")
        
        if not self.token_data or 'refresh_token' not in self.token_data:
            logger.warning("No refresh token available, getting new token")
            return self._get_new_token()
        
        try:
            # Prepare the request
            auth_string = f"{self.client_id}:{self.client_secret}"
            encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.token_data['refresh_token']
            }
            
            # Make the request
            response = requests.post(self.token_url, headers=headers, data=data)
            
            # Check for errors
            if response.status_code != 200:
                logger.warning(f"Token refresh failed: {response.status_code} - {response.text}")
                logger.warning("Getting new token instead")
                return self._get_new_token()
            
            # Parse the response
            token_data = response.json()
            
            # Add expiration time
            token_data['expires_at'] = time.time() + token_data.get('expires_in', 3600)
            
            # Store the token
            self.token_data = token_data
            
            # Save to cache
            self._save_token_to_cache()
            
            logger.info("Successfully refreshed token")
            return token_data
        
        except Exception as e:
            logger.warning(f"Error refreshing token: {str(e)}")
            logger.warning("Getting new token instead")
            return self._get_new_token()
    
    def get_auth_header(self):
        """
        Get the authorization header value
        
        Returns:
            str: Bearer token
        """
        logger.debug("Getting auth header")
        
        # Check if we have a valid token
        if not self._is_token_valid():
            # Try to refresh the token
            if self.token_data and 'refresh_token' in self.token_data:
                logger.debug("Token expired, refreshing")
                self._refresh_token()
            else:
                # Get a new token
                logger.debug("No valid token, getting new one")
                self._get_new_token()
        else:
            logger.debug("Using cached token")
        
        # Return the access token
        return self.token_data.get('access_token', '')
    
    def clear_token_cache(self):
        """Clear the token cache file."""
        self.token_data = None
        
        if os.path.exists(self.token_cache_path):
            try:
                os.remove(self.token_cache_path)
                logger.info("Cleared token cache")
            except Exception as e:
                logger.error(f"Error clearing token cache: {str(e)}")