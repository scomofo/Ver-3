import os
import json
import base64
import time
import logging
import requests

# Set up logger
logger = logging.getLogger('JDQuoteApp.OAuth')

class JDOAuthClient:
    """
    OAuth 2.0 client for John Deere API authentication
    Handles token acquisition and renewal
    """
    
    def __init__(self, client_id, client_secret, token_url=None, token_cache_path=None):
        """
        Initialize the OAuth client
        
        Args:
            client_id (str): Client ID from John Deere Developer portal
            client_secret (str): Client Secret from John Deere Developer portal
            token_url (str, optional): Token endpoint URL
            token_cache_path (str, optional): Path to store token cache
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url or "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"
        
        # Remove any trailing whitespace or newlines from credentials
        if self.client_id:
            self.client_id = self.client_id.strip()
        if self.client_secret:
            self.client_secret = self.client_secret.strip()
        
        # Set up token cache
        self.token_cache_path = token_cache_path
        if self.token_cache_path is None:
            # Default cache location
            cache_dir = os.path.join(os.path.expanduser("~"), ".jd_quote_app")
            os.makedirs(cache_dir, exist_ok=True)
            self.token_cache_path = os.path.join(cache_dir, "token_cache.json")
        
        # Internal token storage
        self.token_data = None
        
        # Load cached token if available
        self._load_token_from_cache()
        
        logger.info(f"OAuth client initialized with client ID: {client_id[:5]}...")
    
    def _load_token_from_cache(self):
        """Load the token from cache file if available."""
        if not self.token_cache_path or not os.path.exists(self.token_cache_path):
            logger.debug("No token cache file found")
            return False
        
        try:
            with open(self.token_cache_path, 'r') as f:
                self.token_data = json.load(f)
            
            # Check if token is expired
            if self._is_token_expired():
                logger.debug("Cached token is expired")
                return False
            
            logger.info("Loaded valid token from cache")
            return True
        except Exception as e:
            logger.error(f"Error loading token from cache: {str(e)}")
            return False
    
    def _save_token_to_cache(self):
        """Save the token to the cache file."""
        if not self.token_cache_path or not self.token_data:
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.token_cache_path), exist_ok=True)
            
            with open(self.token_cache_path, 'w') as f:
                json.dump(self.token_data, f)
            
            logger.info("Token saved to cache")
            return True
        except Exception as e:
            logger.error(f"Error saving token to cache: {str(e)}")
            return False
    
    def _is_token_expired(self):
        """Check if the current token is expired or about to expire."""
        if not self.token_data:
            return True
        
        # Check expiry timestamp if available
        if 'expires_at' in self.token_data:
            # Add buffer of 5 minutes to be safe
            return time.time() >= (self.token_data['expires_at'] - 300)
        
        # If no expiry info, assume expired
        return True
    
    def _get_new_token(self):
        """
        Get a new token from the authorization server.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client_id or not self.client_secret:
            logger.error("Client ID and Client Secret are required")
            raise ValueError("Client ID and Client Secret are required")
        
        # Create authorization header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        # Set up headers and data
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Request data - use only scopes known to work
        data = {
            "grant_type": "client_credentials",
            "scope": "offline_access axiom"
        }
        
        logger.info("Getting new token")
        
        try:
            response = requests.post(
                self.token_url, 
                headers=headers, 
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                self.token_data = response.json()
                
                # Add expiry timestamp for easier checking
                if 'expires_in' in self.token_data:
                    self.token_data['expires_at'] = time.time() + self.token_data['expires_in']
                
                # Save token to cache
                self._save_token_to_cache()
                
                logger.info("Successfully acquired new token")
                return True
            else:
                logger.error(f"Token request failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get token: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
    
    def get_access_token(self):
        """
        Get the current access token, refreshing if necessary.
        
        Returns:
            str: The access token
        """
        # Check if token is valid
        if self._is_token_expired():
            # Get a new token
            self._get_new_token()
        
        # Return the access token
        if self.token_data and 'access_token' in self.token_data:
            return self.token_data['access_token']
        else:
            logger.error("No valid token available")
            raise Exception("No valid token available")
    
    def get_auth_header(self):
        """
        Get the authorization header for API requests.
        
        Returns:
            dict: Headers including Authorization
        """
        try:
            # Get current token
            token = self.get_access_token()
            
            if self._is_token_expired():
                logger.debug("Using cached token")
            else:
                logger.debug("Using new token")
            
            # Return headers
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        except Exception as e:
            logger.error(f"Error creating auth header: {str(e)}")
            raise

# For testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.DEBUG, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Get credentials from environment variables
    client_id = os.getenv('JD_CLIENT_ID')
    client_secret = os.getenv('DEERE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("Error: JD_CLIENT_ID and DEERE_CLIENT_SECRET environment variables must be set")
        exit(1)
    
    # Create OAuth client
    oauth_client = JDOAuthClient(client_id, client_secret)
    
    try:
        # Get authorization header
        headers = oauth_client.get_auth_header()
        
        print("Successfully obtained authorization header:")
        print(f"Authorization: Bearer {headers['Authorization'][7:15]}...")
        
        print("OAuth client is working correctly!")
        
    except Exception as e:
        print(f"Error: {str(e)}")