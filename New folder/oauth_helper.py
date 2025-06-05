# api/oauth_helper.py - New file to handle JD OAuth authentication

import os
import base64
import json
import time
import logging
import requests
from datetime import datetime

class JDOAuthHelper:
    """Helper for John Deere OAuth authentication."""
    
    # OAuth endpoints from documentation
    TOKEN_URL = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"
    
    def __init__(self, cache_path=None, logger=None):
        """Initialize the OAuth helper.
        
        Args:
            cache_path: Path to cache directory for storing tokens
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Get credentials from environment
        self.client_id = os.getenv('JD_CLIENT_ID', '0oao5jntk71YDUX9Q5d7')
        self.client_secret = os.getenv('DEERE_CLIENT_SECRET', 'DllrCc0lm1rFj1-gcpYBA03YemkGXohWX2Q3Q7PyA3urj7Gu7VUda6153JPf54tO')
        
        # Set up token cache
        self.cache_path = cache_path
        if self.cache_path:
            os.makedirs(self.cache_path, exist_ok=True)
            self.token_file = os.path.join(self.cache_path, "jd_token.json")
        else:
            self.token_file = None
            
        self.logger.info(f"JDOAuthHelper initialized with client ID: {self.client_id[:8]}...")
    
    def get_token(self, force_refresh=False):
        """Get a valid token, using cache if available.
        
        Args:
            force_refresh: Force getting a new token even if cached one exists
            
        Returns:
            Token string or None if failed
        """
        if not force_refresh:
            # Try to load from cache first
            cached_token = self.load_cached_token()
            if cached_token:
                return cached_token
        
        # Get a new token
        token_data = self.get_client_credentials_token()
        if token_data:
            return token_data.get('access_token')
        
        return None
        
    def load_cached_token(self):
        """Load a token from cache if available and not expired.
        
        Returns:
            Token string or None if no valid cached token
        """
        if not self.token_file or not os.path.exists(self.token_file):
            self.logger.info("No cached token file found")
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # Check if token has expired (with 5-minute buffer)
            if 'expires_at' in token_data and token_data['expires_at'] > time.time() + 300:
                self.logger.info("Using cached token")
                return token_data.get('access_token')
            else:
                self.logger.info("Cached token has expired")
                return None
        except Exception as e:
            self.logger.error(f"Error loading cached token: {str(e)}")
            return None
            
    def get_client_credentials_token(self):
        """Get a token using the client credentials grant type.
        
        Returns:
            dict with token information or None if failed
        """
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
        
        data = {
            "grant_type": "client_credentials",
            "scope": "offline_access"
        }
        
        try:
            self.logger.info(f"Requesting access token from {self.TOKEN_URL}")
            response = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                # Add expiry timestamp
                if 'expires_in' in token_data:
                    token_data['expires_at'] = time.time() + token_data['expires_in']
                
                self.logger.info(f"Successfully obtained access token (expires in {token_data.get('expires_in', 'unknown')} seconds)")
                
                # Save token to cache
                if self.token_file:
                    try:
                        with open(self.token_file, 'w') as f:
                            json.dump(token_data, f)
                        self.logger.info(f"Saved token to {self.token_file}")
                    except Exception as e:
                        self.logger.error(f"Error saving token to cache: {str(e)}")
                
                return token_data
            else:
                self.logger.error(f"Failed to get token: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting token: {str(e)}")
            return None