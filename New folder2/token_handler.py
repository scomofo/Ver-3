# utils/token_handler.py
# Fixed TokenHandler implementation to accept config parameter

import os
import json
import time
import requests
import logging
from datetime import datetime, timedelta

# Get a logger instance
logger = logging.getLogger('BCApp.TokenHandler')

class TokenHandler:
    """
    Manages authentication tokens for Microsoft Graph API / SharePoint access.
    Handles token acquisition, caching, and renewal.
    """
    
    def __init__(self, config=None):
        """
        Initialize the TokenHandler.
        
        Args:
            config (Config, optional): Application configuration object. Defaults to None.
        """
        self.config = config
        self.tokens = {}  # Dictionary to store tokens: {resource: {token_data}}
        self.token_file = None
        
        # Set up token cache file path
        if config and hasattr(config, 'cache_dir'):
            self.token_file = os.path.join(config.cache_dir, 'tokens.json')
            logger.debug(f"Using token cache file: {self.token_file}")
        else:
            # Try to find a suitable location for token cache
            cache_locations = [
                os.path.join(os.getcwd(), 'cache'),
                os.path.expanduser('~/.cache/bcapp')
            ]
            
            for location in cache_locations:
                if not os.path.exists(location):
                    try:
                        os.makedirs(location, exist_ok=True)
                        self.token_file = os.path.join(location, 'tokens.json')
                        logger.debug(f"Created token cache location: {self.token_file}")
                        break
                    except OSError:
                        continue
                else:
                    self.token_file = os.path.join(location, 'tokens.json')
                    logger.debug(f"Using existing token cache location: {self.token_file}")
                    break
        
        # Load cached tokens if available
        self._load_tokens()
    
    def _load_tokens(self):
        """Load tokens from cache file if available."""
        if not self.token_file:
            logger.warning("No token file path configured. Cannot load cached tokens.")
            return
            
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    self.tokens = json.load(f)
                logger.info(f"Loaded cached tokens for resources: {list(self.tokens.keys())}")
            else:
                logger.info("No cached tokens file found. Starting with empty token cache.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading token cache file: {e}")
            self.tokens = {}  # Reset to empty dict on error
            
    def _save_tokens(self):
        """Save tokens to cache file."""
        if not self.token_file:
            logger.warning("No token file path configured. Cannot save tokens.")
            return
            
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            
            with open(self.token_file, 'w') as f:
                json.dump(self.tokens, f)
            logger.debug("Tokens saved to cache file")
        except IOError as e:
            logger.error(f"Error saving token cache file: {e}")
    
    def get_access_token(self, resource="sharepoint"):
        """
        Get a valid access token for the specified resource.
        
        Args:
            resource (str): The resource identifier (e.g., "sharepoint", "graph").
                           Defaults to "sharepoint".
        
        Returns:
            str or dict: The access token string or token details dictionary if available,
                        None if acquisition fails.
        """
        # Check if we have a valid cached token
        if resource in self.tokens:
            token_data = self.tokens[resource]
            expiry_time = token_data.get('expires_at', 0)
            
            # If token is still valid (with 5 min buffer)
            if expiry_time > time.time() + 300:
                logger.debug(f"Using cached token for {resource}")
                return token_data
        
        # No valid token found, acquire a new one
        token_data = self._acquire_token(resource)
        
        if token_data:
            # Cache the token with expiry time
            self.tokens[resource] = token_data
            self._save_tokens()
            return token_data
        
        logger.error(f"Failed to acquire token for {resource}")
        return None
    
    def _acquire_token(self, resource):
        """
        Acquire a new token for the specified resource.
        
        Args:
            resource (str): The resource identifier.
        
        Returns:
            dict: Token data if successful, None otherwise.
        """
        # Each resource might have different auth methods
        if resource == "sharepoint":
            return self._get_sharepoint_token()
        elif resource == "graph":
            return self._get_graph_token()
        else:
            logger.warning(f"Unknown resource type: {resource}")
            return None
    
    def _get_sharepoint_token(self):
        """
        Acquire a SharePoint/Graph API token.
        
        Returns:
            dict: Token data if successful, None otherwise.
        """
        # Get credentials from environment or config
        client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
        
        # Try fallback to config if environment variables not set
        if not all([client_id, client_secret, tenant_id]) and self.config:
            client_id = getattr(self.config, 'sharepoint_client_id', None) or client_id
            client_secret = getattr(self.config, 'sharepoint_client_secret', None) or client_secret
            tenant_id = getattr(self.config, 'sharepoint_tenant_id', None) or tenant_id
        
        if not all([client_id, client_secret, tenant_id]):
            logger.error("Missing SharePoint credentials. Check environment variables or config.")
            return None
        
        # Acquire token using client credentials flow
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        scope = "https://graph.microsoft.com/.default"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope
        }
        
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            # Add expiry time for our cache validation
            if 'expires_in' in token_data:
                token_data['expires_at'] = time.time() + token_data['expires_in']
            
            logger.info("Successfully acquired SharePoint token")
            return token_data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error acquiring SharePoint token: {e}")
            return None
    
    def _get_graph_token(self):
        """
        Acquire a Microsoft Graph API token (can be more specific to Graph API needs).
        
        Returns:
            dict: Token data if successful, None otherwise.
        """
        # For now, we use the same token as SharePoint
        # In a more complex app, this could be customized for specific Graph API scopes
        return self._get_sharepoint_token()
    
    def clear_token_cache(self, resource=None):
        """
        Clear token cache for a specific resource or all resources.
        
        Args:
            resource (str, optional): Resource to clear cache for. If None, clears all.
        """
        if resource:
            if resource in self.tokens:
                del self.tokens[resource]
                logger.info(f"Cleared token cache for {resource}")
        else:
            self.tokens = {}
            logger.info("Cleared all token caches")
        
        self._save_tokens()
    
    def refresh_token(self, resource="sharepoint"):
        """
        Force refresh a token regardless of expiry.
        
        Args:
            resource (str): Resource to refresh token for.
            
        Returns:
            dict: New token data if successful, None otherwise.
        """
        # Clear existing token if any
        if resource in self.tokens:
            del self.tokens[resource]
        
        # Acquire fresh token
        token_data = self._acquire_token(resource)
        
        if token_data:
            self.tokens[resource] = token_data
            self._save_tokens()
            logger.info(f"Successfully refreshed token for {resource}")
            return token_data
        
        logger.error(f"Failed to refresh token for {resource}")
        return None